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
