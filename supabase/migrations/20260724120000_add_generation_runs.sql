create type public.generation_action as enum ('plan', 'produce');
create type public.generation_run_status as enum (
  'pending',
  'running',
  'completed',
  'failed'
);

create table public.generation_runs (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  action public.generation_action not null,
  plan_id uuid references public.tour_plan_revisions(id),
  feedback text,
  status public.generation_run_status not null default 'pending',
  attempt integer not null default 0,
  idempotency_key text not null unique,
  error_message text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (action = 'plan')
    or (action = 'produce' and plan_id is not null and feedback is null)
  )
);

create index generation_runs_tour_created_idx
  on public.generation_runs(tour_id, created_at desc);
create index generation_runs_pending_idx
  on public.generation_runs(status, created_at)
  where status in ('pending', 'running');

create trigger generation_runs_set_updated_at
before update on public.generation_runs
for each row execute function public.set_updated_at();

alter table public.generation_runs enable row level security;

revoke all on public.generation_runs from anon, authenticated;
grant all on public.generation_runs to service_role;

create function public.enqueue_tour_creation(
  p_owner_id uuid,
  p_location text,
  p_request text,
  p_voice text,
  p_voice_style text,
  p_tts_model text,
  p_audio_format text,
  p_idempotency_key text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_tour public.tours;
  v_run public.generation_runs;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_idempotency_key, 0));

  select runs.* into v_run
  from public.generation_runs as runs
  join public.tours as tours on tours.id = runs.tour_id
  where runs.idempotency_key = p_idempotency_key
    and tours.owner_id = p_owner_id;

  if found then
    return jsonb_build_object('tour_id', v_run.tour_id, 'run_id', v_run.id);
  end if;

  insert into public.tours (
    owner_id,
    location,
    request,
    status,
    voice,
    voice_style,
    tts_model,
    audio_format,
    progress_message
  ) values (
    p_owner_id,
    trim(p_location),
    trim(p_request),
    'researching',
    coalesce(nullif(trim(p_voice), ''), 'Kore'),
    nullif(trim(p_voice_style), ''),
    nullif(trim(p_tts_model), ''),
    coalesce(nullif(trim(p_audio_format), ''), 'wav'),
    'Queued for checkpoint research'
  ) returning * into v_tour;

  insert into public.generation_runs (
    tour_id,
    action,
    idempotency_key
  ) values (
    v_tour.id,
    'plan',
    p_idempotency_key
  ) returning * into v_run;

  return jsonb_build_object('tour_id', v_tour.id, 'run_id', v_run.id);
end;
$$;

create function public.enqueue_tour_feedback(
  p_owner_id uuid,
  p_tour_id uuid,
  p_plan_id uuid,
  p_feedback text,
  p_idempotency_key text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_tour public.tours;
  v_run public.generation_runs;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_idempotency_key, 0));

  select * into v_run
  from public.generation_runs
  where idempotency_key = p_idempotency_key
    and tour_id = p_tour_id;

  if found then
    return jsonb_build_object('tour_id', v_run.tour_id, 'run_id', v_run.id);
  end if;

  select * into v_tour
  from public.tours
  where id = p_tour_id and owner_id = p_owner_id
  for update;

  if not found then
    raise exception 'Tour not found';
  end if;
  if v_tour.status <> 'awaiting_review' then
    raise exception 'Tour cannot accept feedback while %', v_tour.status;
  end if;
  if v_tour.current_plan_revision - 1 >= 3 then
    raise exception 'A tour can have at most 3 feedback rounds';
  end if;

  if not exists (
    select 1 from public.tour_plan_revisions
    where id = p_plan_id
      and tour_id = p_tour_id
      and revision = v_tour.current_plan_revision
  ) then
    raise exception 'Feedback must target the current tour plan';
  end if;

  insert into public.generation_runs (
    tour_id,
    action,
    plan_id,
    feedback,
    idempotency_key
  ) values (
    p_tour_id,
    'plan',
    p_plan_id,
    trim(p_feedback),
    p_idempotency_key
  ) returning * into v_run;

  update public.tours set
    status = 'researching',
    progress_message = 'Queued to revise checkpoints from your feedback',
    progress_current = null,
    progress_total = null,
    error_message = null
  where id = p_tour_id;

  return jsonb_build_object('tour_id', p_tour_id, 'run_id', v_run.id);
end;
$$;

create function public.enqueue_tour_production(
  p_owner_id uuid,
  p_tour_id uuid,
  p_plan_id uuid,
  p_idempotency_key text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_tour public.tours;
  v_run public.generation_runs;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_idempotency_key, 0));

  select * into v_run
  from public.generation_runs
  where idempotency_key = p_idempotency_key
    and tour_id = p_tour_id;

  if found then
    return jsonb_build_object('tour_id', v_run.tour_id, 'run_id', v_run.id);
  end if;

  select * into v_tour
  from public.tours
  where id = p_tour_id and owner_id = p_owner_id
  for update;

  if not found then
    raise exception 'Tour not found';
  end if;
  if v_tour.status <> 'awaiting_review' then
    raise exception 'Tour cannot be approved while %', v_tour.status;
  end if;
  if not exists (
    select 1 from public.tour_plan_revisions
    where id = p_plan_id
      and tour_id = p_tour_id
      and revision = v_tour.current_plan_revision
  ) then
    raise exception 'The approved plan is not the current tour plan';
  end if;

  perform public.begin_tour_production(p_tour_id, p_plan_id);

  insert into public.generation_runs (
    tour_id,
    action,
    plan_id,
    idempotency_key
  ) values (
    p_tour_id,
    'produce',
    p_plan_id,
    p_idempotency_key
  ) returning * into v_run;

  return jsonb_build_object('tour_id', p_tour_id, 'run_id', v_run.id);
end;
$$;

create function public.claim_generation_run(p_run_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_run public.generation_runs;
begin
  update public.generation_runs set
    status = 'running',
    attempt = attempt + 1,
    started_at = now(),
    error_message = null
  where id = p_run_id and status = 'pending'
  returning * into v_run;

  if not found then
    return null;
  end if;
  return to_jsonb(v_run);
end;
$$;

create function public.complete_generation_run(p_run_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.generation_runs set
    status = 'completed',
    completed_at = now(),
    error_message = null
  where id = p_run_id and status = 'running';
end;
$$;

create function public.fail_generation_run(p_run_id uuid, p_error_message text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.generation_runs set
    status = 'failed',
    completed_at = now(),
    error_message = left(p_error_message, 2000)
  where id = p_run_id and status in ('pending', 'running');
end;
$$;

revoke all on function public.enqueue_tour_creation(uuid, text, text, text, text, text, text, text) from public;
revoke all on function public.enqueue_tour_feedback(uuid, uuid, uuid, text, text) from public;
revoke all on function public.enqueue_tour_production(uuid, uuid, uuid, text) from public;
revoke all on function public.claim_generation_run(uuid) from public;
revoke all on function public.complete_generation_run(uuid) from public;
revoke all on function public.fail_generation_run(uuid, text) from public;

grant execute on function public.enqueue_tour_creation(uuid, text, text, text, text, text, text, text) to service_role;
grant execute on function public.enqueue_tour_feedback(uuid, uuid, uuid, text, text) to service_role;
grant execute on function public.enqueue_tour_production(uuid, uuid, uuid, text) to service_role;
grant execute on function public.claim_generation_run(uuid) to service_role;
grant execute on function public.complete_generation_run(uuid) to service_role;
grant execute on function public.fail_generation_run(uuid, text) to service_role;
