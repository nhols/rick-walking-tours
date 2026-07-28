create or replace function public.persist_tour_plan(
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

  insert into public.tour_plan_revisions (
    tour_id, revision, feedback, payload, new_agent_messages
  ) values (
    p_tour_id, v_revision, p_feedback, p_payload, p_new_agent_messages
  ) returning id into v_plan_id;

  perform public.record_tour_status(p_tour_id, 'awaiting_review');
  return v_plan_id;
end;
$$;

create or replace function public.enqueue_tour_feedback(
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

  select id into v_current_plan_id
  from public.tour_plan_revisions
  where tour_id = p_tour_id
  order by revision desc
  limit 1;
  if p_plan_id is distinct from v_current_plan_id then
    raise exception 'Feedback must target the current tour plan';
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
