create or replace function public.begin_tour_production(
  p_tour_id uuid,
  p_plan_id uuid
)
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

  -- Different tours do not share a row lock. Serialize credit spending by owner
  -- so concurrent approvals cannot both observe and spend the same balance.
  perform pg_advisory_xact_lock(
    hashtextextended(
      'tour-production-credit:' || v_tour.owner_id::text,
      0
    )
  );

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

create or replace function public.enqueue_tour_production(
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
  v_should_produce boolean;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_idempotency_key, 0));

  select * into v_job from public.tour_jobs
  where idempotency_key = p_idempotency_key and tour_id = p_tour_id;
  if found then
    return jsonb_build_object(
      'tour_id', v_job.tour_id,
      'job_id', v_job.id,
      'invoke_worker', v_job.status = 'pending'
    );
  end if;

  perform 1 from public.tours
  where id = p_tour_id and owner_id = p_owner_id;
  if not found then
    raise exception 'Tour not found';
  end if;

  v_should_produce := public.begin_tour_production(p_tour_id, p_plan_id);
  if not v_should_produce then
    select * into v_job
    from public.tour_jobs
    where tour_id = p_tour_id
      and payload ->> 'kind' = 'produce'
      and payload ->> 'plan_id' = p_plan_id::text
    order by created_at desc
    limit 1;
    if not found then
      raise exception 'Completed tour has no production job';
    end if;

    return jsonb_build_object(
      'tour_id', p_tour_id,
      'job_id', v_job.id,
      'invoke_worker', false
    );
  end if;

  insert into public.tour_jobs (tour_id, payload, idempotency_key)
  values (
    p_tour_id,
    jsonb_build_object('kind', 'produce', 'plan_id', p_plan_id),
    p_idempotency_key
  ) returning * into v_job;

  return jsonb_build_object(
    'tour_id', p_tour_id,
    'job_id', v_job.id,
    'invoke_worker', true
  );
end;
$$;
