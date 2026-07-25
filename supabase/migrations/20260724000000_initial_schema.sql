create table public.tours (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'researching',
  title text,
  input jsonb not null check (jsonb_typeof(input) = 'object'),
  approved_plan_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index tours_owner_created_idx on public.tours(owner_id, created_at desc);

create table public.tour_status_events (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  status text not null,
  details jsonb,
  created_at timestamptz not null default now(),
  check (details is null or jsonb_typeof(details) = 'object')
);

create index tour_status_events_tour_created_idx
  on public.tour_status_events(tour_id, created_at desc);

create table public.tour_plan_revisions (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  revision integer not null check (revision > 0),
  feedback text,
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  new_agent_messages jsonb not null default '[]'::jsonb
    check (jsonb_typeof(new_agent_messages) = 'array'),
  created_at timestamptz not null default now(),
  unique (tour_id, revision),
  check (
    (revision = 1 and feedback is null)
    or
    (revision > 1 and nullif(btrim(feedback), '') is not null)
  )
);

alter table public.tours
  add constraint tours_approved_plan_fk
  foreign key (approved_plan_id) references public.tour_plan_revisions(id);

create table public.tour_outputs (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  plan_id uuid not null references public.tour_plan_revisions(id) on delete cascade,
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  created_at timestamptz not null default now(),
  unique (tour_id, plan_id)
);

create table public.credit_transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  delta integer not null check (delta <> 0),
  reason text not null,
  tour_id uuid references public.tours(id),
  idempotency_key text not null unique,
  created_at timestamptz not null default now()
);

create index credit_transactions_user_idx
  on public.credit_transactions(user_id, created_at desc);

create table public.tour_jobs (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  payload jsonb not null check (
    jsonb_typeof(payload) = 'object'
    and payload ? 'kind'
    and payload ->> 'kind' in ('plan', 'revise', 'produce')
  ),
  status text not null default 'pending'
    check (status in ('pending', 'running', 'completed', 'failed')),
  idempotency_key text not null unique,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);

create index tour_jobs_pending_idx on public.tour_jobs(created_at)
  where status = 'pending';

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'tour-audio',
  'tour-audio',
  false,
  104857600,
  array['audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/ogg']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger tours_set_updated_at
before update on public.tours
for each row execute function public.set_updated_at();

create function public.record_tour_status(
  p_tour_id uuid,
  p_status text,
  p_details jsonb default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_details is not null and jsonb_typeof(p_details) <> 'object' then
    raise exception 'Status details must be a JSON object';
  end if;

  update public.tours set status = p_status where id = p_tour_id;
  if not found then
    raise exception 'Tour not found';
  end if;

  insert into public.tour_status_events (tour_id, status, details)
  values (p_tour_id, p_status, p_details);
end;
$$;

create function public.persist_tour_plan(
  p_tour_id uuid,
  p_feedback text,
  p_payload jsonb,
  p_new_agent_messages jsonb
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_tour public.tours;
  v_plan_id uuid;
  v_revision integer;
begin
  select * into v_tour from public.tours where id = p_tour_id for update;
  if not found then
    raise exception 'Tour not found';
  end if;
  if v_tour.status <> 'researching' then
    raise exception 'Tour cannot accept a plan while %', v_tour.status;
  end if;
  if jsonb_typeof(p_payload) is distinct from 'object' then
    raise exception 'Plan payload must be a JSON object';
  end if;
  if jsonb_typeof(p_new_agent_messages) is distinct from 'array' then
    raise exception 'Agent messages must be a JSON array';
  end if;

  select count(*) + 1 into v_revision
  from public.tour_plan_revisions
  where tour_id = p_tour_id;

  if v_revision = 1 and p_feedback is not null then
    raise exception 'The initial plan cannot have feedback';
  end if;
  if v_revision > 1 and nullif(btrim(p_feedback), '') is null then
    raise exception 'Feedback is required for a revised plan';
  end if;
  if v_revision > 4 then
    raise exception 'A tour can have at most 3 feedback rounds';
  end if;

  insert into public.tour_plan_revisions (
    tour_id, revision, feedback, payload, new_agent_messages
  ) values (
    p_tour_id, v_revision, p_feedback, p_payload, p_new_agent_messages
  ) returning id into v_plan_id;

  perform public.record_tour_status(p_tour_id, 'awaiting_review');
  return v_plan_id;
end;
$$;

create function public.begin_tour_production(p_tour_id uuid, p_plan_id uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_tour public.tours;
  v_current_plan_id uuid;
  v_balance bigint;
begin
  select * into v_tour from public.tours where id = p_tour_id for update;
  if not found then
    raise exception 'Tour not found';
  end if;

  select id into v_current_plan_id
  from public.tour_plan_revisions
  where tour_id = p_tour_id
  order by revision desc
  limit 1;

  if p_plan_id is distinct from v_current_plan_id then
    raise exception 'The approved plan is not the current tour plan';
  end if;
  if v_tour.status = 'ready' and v_tour.approved_plan_id = p_plan_id then
    return false;
  end if;
  if v_tour.status <> 'awaiting_review' then
    raise exception 'Tour cannot be approved while %', v_tour.status;
  end if;

  select coalesce(sum(delta), 0) into v_balance
  from public.credit_transactions
  where user_id = v_tour.owner_id;
  if v_balance < 1 then
    raise exception 'Insufficient credits';
  end if;

  insert into public.credit_transactions (
    user_id, delta, reason, tour_id, idempotency_key
  ) values (
    v_tour.owner_id, -1, 'tour_generation', p_tour_id,
    'tour-production:' || p_tour_id::text
  );

  update public.tours set approved_plan_id = p_plan_id where id = p_tour_id;
  perform public.record_tour_status(p_tour_id, 'writing_chapters');
  return true;
end;
$$;

create function public.save_tour_output(
  p_tour_id uuid,
  p_plan_id uuid,
  p_title text,
  p_payload jsonb,
  p_status text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_status not in ('generating_audio', 'ready') then
    raise exception 'Invalid output status';
  end if;
  if jsonb_typeof(p_payload) is distinct from 'object' then
    raise exception 'Tour output must be a JSON object';
  end if;
  if not exists (
    select 1 from public.tours
    where id = p_tour_id and approved_plan_id = p_plan_id
  ) then
    raise exception 'Tour plan is not approved';
  end if;

  insert into public.tour_outputs (tour_id, plan_id, payload)
  values (p_tour_id, p_plan_id, p_payload)
  on conflict (tour_id, plan_id) do update set payload = excluded.payload;

  update public.tours set title = nullif(btrim(p_title), '') where id = p_tour_id;
  perform public.record_tour_status(p_tour_id, p_status);
end;
$$;

create function public.enqueue_tour_creation(
  p_owner_id uuid,
  p_input jsonb,
  p_idempotency_key text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_tour_id uuid;
  v_job public.tour_jobs;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_idempotency_key, 0));

  select jobs.* into v_job
  from public.tour_jobs as jobs
  join public.tours as tours on tours.id = jobs.tour_id
  where jobs.idempotency_key = p_idempotency_key
    and tours.owner_id = p_owner_id;
  if found then
    return jsonb_build_object('tour_id', v_job.tour_id, 'job_id', v_job.id);
  end if;

  if jsonb_typeof(p_input) is distinct from 'object'
    or nullif(btrim(p_input ->> 'location'), '') is null
    or nullif(btrim(p_input ->> 'request'), '') is null then
    raise exception 'Tour input requires a location and request';
  end if;

  insert into public.tours (owner_id, input)
  values (p_owner_id, p_input)
  returning id into v_tour_id;

  insert into public.tour_status_events (tour_id, status)
  values (v_tour_id, 'researching');

  insert into public.tour_jobs (tour_id, payload, idempotency_key)
  values (v_tour_id, jsonb_build_object('kind', 'plan'), p_idempotency_key)
  returning * into v_job;

  return jsonb_build_object('tour_id', v_tour_id, 'job_id', v_job.id);
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
  v_current_plan_id uuid;
  v_current_revision integer;
  v_job public.tour_jobs;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_idempotency_key, 0));

  select * into v_job from public.tour_jobs
  where idempotency_key = p_idempotency_key and tour_id = p_tour_id;
  if found then
    return jsonb_build_object('tour_id', v_job.tour_id, 'job_id', v_job.id);
  end if;

  select * into v_tour from public.tours
  where id = p_tour_id and owner_id = p_owner_id for update;
  if not found then
    raise exception 'Tour not found';
  end if;
  if v_tour.status <> 'awaiting_review' then
    raise exception 'Tour cannot accept feedback while %', v_tour.status;
  end if;

  select id, revision into v_current_plan_id, v_current_revision
  from public.tour_plan_revisions
  where tour_id = p_tour_id
  order by revision desc
  limit 1;
  if p_plan_id is distinct from v_current_plan_id then
    raise exception 'Feedback must target the current tour plan';
  end if;
  if v_current_revision >= 4 then
    raise exception 'A tour can have at most 3 feedback rounds';
  end if;
  if nullif(btrim(p_feedback), '') is null then
    raise exception 'Feedback is required';
  end if;

  insert into public.tour_jobs (tour_id, payload, idempotency_key)
  values (
    p_tour_id,
    jsonb_build_object(
      'kind', 'revise',
      'plan_id', p_plan_id,
      'feedback', btrim(p_feedback)
    ),
    p_idempotency_key
  ) returning * into v_job;

  perform public.record_tour_status(p_tour_id, 'researching');
  return jsonb_build_object('tour_id', p_tour_id, 'job_id', v_job.id);
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
  v_job public.tour_jobs;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_idempotency_key, 0));

  select * into v_job from public.tour_jobs
  where idempotency_key = p_idempotency_key and tour_id = p_tour_id;
  if found then
    return jsonb_build_object('tour_id', v_job.tour_id, 'job_id', v_job.id);
  end if;

  perform 1 from public.tours
  where id = p_tour_id and owner_id = p_owner_id;
  if not found then
    raise exception 'Tour not found';
  end if;

  perform public.begin_tour_production(p_tour_id, p_plan_id);

  insert into public.tour_jobs (tour_id, payload, idempotency_key)
  values (
    p_tour_id,
    jsonb_build_object('kind', 'produce', 'plan_id', p_plan_id),
    p_idempotency_key
  ) returning * into v_job;

  return jsonb_build_object('tour_id', p_tour_id, 'job_id', v_job.id);
end;
$$;

create function public.claim_tour_job(p_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_job public.tour_jobs;
begin
  update public.tour_jobs set status = 'running', started_at = now()
  where id = p_job_id and status = 'pending'
  returning * into v_job;

  if not found then
    return null;
  end if;
  return to_jsonb(v_job);
end;
$$;

create function public.complete_tour_job(p_job_id uuid)
returns void
language sql
security definer
set search_path = ''
as $$
  update public.tour_jobs
  set status = 'completed', completed_at = now()
  where id = p_job_id and status = 'running';
$$;

create function public.fail_tour_job(p_job_id uuid)
returns void
language sql
security definer
set search_path = ''
as $$
  update public.tour_jobs
  set status = 'failed', completed_at = now()
  where id = p_job_id and status in ('pending', 'running');
$$;

alter table public.tours enable row level security;
alter table public.tour_status_events enable row level security;
alter table public.tour_plan_revisions enable row level security;
alter table public.tour_outputs enable row level security;
alter table public.credit_transactions enable row level security;
alter table public.tour_jobs enable row level security;

create policy tours_select_own on public.tours
for select to authenticated using (owner_id = auth.uid());

create policy tour_status_events_select_own on public.tour_status_events
for select to authenticated using (
  exists (
    select 1 from public.tours
    where tours.id = tour_status_events.tour_id
      and tours.owner_id = auth.uid()
  )
);

create policy plans_select_own on public.tour_plan_revisions
for select to authenticated using (
  exists (
    select 1 from public.tours
    where tours.id = tour_plan_revisions.tour_id
      and tours.owner_id = auth.uid()
  )
);

create policy outputs_select_own on public.tour_outputs
for select to authenticated using (
  exists (
    select 1 from public.tours
    where tours.id = tour_outputs.tour_id
      and tours.owner_id = auth.uid()
  )
);

create policy credits_select_own on public.credit_transactions
for select to authenticated using (user_id = auth.uid());

create policy tour_audio_select_own on storage.objects
for select to authenticated using (
  bucket_id = 'tour-audio'
  and (storage.foldername(name))[1] = auth.uid()::text
);

revoke all on public.tours,
  public.tour_status_events,
  public.tour_plan_revisions,
  public.tour_outputs,
  public.credit_transactions,
  public.tour_jobs
from anon, authenticated;

grant select on public.tours,
  public.tour_status_events,
  public.tour_outputs,
  public.credit_transactions
to authenticated;

grant select (id, tour_id, revision, feedback, payload, created_at)
on public.tour_plan_revisions to authenticated;

grant all on public.tours,
  public.tour_status_events,
  public.tour_plan_revisions,
  public.tour_outputs,
  public.credit_transactions,
  public.tour_jobs
to service_role;

revoke all on function public.record_tour_status(uuid, text, jsonb) from public;
revoke all on function public.persist_tour_plan(uuid, text, jsonb, jsonb) from public;
revoke all on function public.begin_tour_production(uuid, uuid) from public;
revoke all on function public.save_tour_output(uuid, uuid, text, jsonb, text) from public;
revoke all on function public.enqueue_tour_creation(uuid, jsonb, text) from public;
revoke all on function public.enqueue_tour_feedback(uuid, uuid, uuid, text, text) from public;
revoke all on function public.enqueue_tour_production(uuid, uuid, uuid, text) from public;
revoke all on function public.claim_tour_job(uuid) from public;
revoke all on function public.complete_tour_job(uuid) from public;
revoke all on function public.fail_tour_job(uuid) from public;

grant execute on function public.record_tour_status(uuid, text, jsonb) to service_role;
grant execute on function public.persist_tour_plan(uuid, text, jsonb, jsonb) to service_role;
grant execute on function public.begin_tour_production(uuid, uuid) to service_role;
grant execute on function public.save_tour_output(uuid, uuid, text, jsonb, text) to service_role;
grant execute on function public.enqueue_tour_creation(uuid, jsonb, text) to service_role;
grant execute on function public.enqueue_tour_feedback(uuid, uuid, uuid, text, text) to service_role;
grant execute on function public.enqueue_tour_production(uuid, uuid, uuid, text) to service_role;
grant execute on function public.claim_tour_job(uuid) to service_role;
grant execute on function public.complete_tour_job(uuid) to service_role;
grant execute on function public.fail_tour_job(uuid) to service_role;
