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
  v_balance bigint;
begin
  select * into v_tour
  from public.tours
  where id = p_tour_id
  for update;

  if not found then
    raise exception 'Tour not found';
  end if;
  if not exists (
    select 1 from public.tour_plan_revisions
    where id = p_plan_id
      and tour_id = p_tour_id
      and revision = v_tour.current_plan_revision
  ) then
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
    user_id,
    delta,
    reason,
    tour_id,
    idempotency_key
  ) values (
    v_tour.owner_id,
    -1,
    'tour_generation',
    p_tour_id,
    'tour-production:' || p_tour_id::text
  );

  update public.tours set
    approved_plan_id = p_plan_id,
    approved_at = now(),
    status = 'writing_chapters',
    progress_message = 'Writing chapters',
    progress_current = null,
    progress_total = null,
    error_message = null
  where id = p_tour_id;
  return true;
end;
$$;
