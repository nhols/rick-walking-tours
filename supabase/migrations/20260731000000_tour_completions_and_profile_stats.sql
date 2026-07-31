create table public.tour_completions (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  completed_at timestamptz not null default now(),
  unique (tour_id, user_id)
);

create index tour_completions_user_completed_idx
  on public.tour_completions(user_id, completed_at desc);

create index tour_completions_tour_completed_idx
  on public.tour_completions(tour_id, completed_at desc);

alter table public.tour_completions enable row level security;

create policy tour_completions_select_own on public.tour_completions
for select to authenticated using (user_id = auth.uid());

create policy tour_completions_delete_own on public.tour_completions
for delete to authenticated using (user_id = auth.uid());

revoke all on public.tour_completions from anon, authenticated;
grant select on public.tour_completions to authenticated;
grant delete on public.tour_completions to authenticated;
grant all on public.tour_completions to service_role;

create function public.complete_tour(p_tour_id uuid)
returns timestamptz
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := auth.uid();
  v_completed_at timestamptz;
begin
  if v_user_id is null then
    raise exception 'Authentication required';
  end if;

  if not exists (
    select 1
    from public.tours
    where id = p_tour_id
      and status = 'ready'
      and (owner_id = v_user_id or is_public)
  ) then
    raise exception 'Ready tour not found';
  end if;

  insert into public.tour_completions (tour_id, user_id)
  values (p_tour_id, v_user_id)
  on conflict (tour_id, user_id) do nothing
  returning completed_at into v_completed_at;

  if v_completed_at is null then
    select completed_at into v_completed_at
    from public.tour_completions
    where tour_id = p_tour_id and user_id = v_user_id;
  end if;

  return v_completed_at;
end;
$$;

revoke all on function public.complete_tour(uuid) from public;
grant execute on function public.complete_tour(uuid) to authenticated;

create function public.get_profile_stats()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with current_user_id as (
    select auth.uid() as id
  ),
  created_tours as (
    select
      count(*) filter (where tours.status = 'ready')::bigint as ready_count,
      count(*) filter (
        where tours.status = 'ready' and tours.is_public
      )::bigint as public_count,
      coalesce(round(sum(
        case when tours.status = 'ready'
          then (plans.payload #>> '{route,distance_meters}')::numeric
        end
      )), 0)::bigint as distance_meters,
      coalesce(round(sum(
        case when tours.status = 'ready'
          then (plans.payload #>> '{route,duration_seconds}')::numeric
        end
      )), 0)::bigint as duration_seconds
    from current_user_id
    left join public.tours on tours.owner_id = current_user_id.id
    left join public.tour_plan_revisions as plans
      on plans.id = tours.approved_plan_id
  ),
  completed_tours as (
    select
      count(completions.id)::bigint as completion_count,
      coalesce(round(sum(
        (plans.payload #>> '{route,distance_meters}')::numeric
      )), 0)::bigint as distance_meters,
      coalesce(round(sum(
        (plans.payload #>> '{route,duration_seconds}')::numeric
      )), 0)::bigint as duration_seconds
    from current_user_id
    left join public.tour_completions as completions
      on completions.user_id = current_user_id.id
    left join public.tours on tours.id = completions.tour_id
    left join public.tour_plan_revisions as plans
      on plans.id = tours.approved_plan_id
  ),
  community_walks as (
    select
      count(completions.id)::bigint as completion_count,
      count(distinct completions.user_id)::bigint as unique_walkers,
      coalesce(round(sum(
        case when completions.id is not null
          then (plans.payload #>> '{route,distance_meters}')::numeric
        end
      )), 0)::bigint as distance_meters,
      coalesce(round(sum(
        case when completions.id is not null
          then (plans.payload #>> '{route,duration_seconds}')::numeric
        end
      )), 0)::bigint as duration_seconds
    from current_user_id
    left join public.tours
      on tours.owner_id = current_user_id.id
      and tours.status = 'ready'
      and tours.is_public
    left join public.tour_completions as completions
      on completions.tour_id = tours.id
      and completions.user_id <> current_user_id.id
    left join public.tour_plan_revisions as plans
      on plans.id = tours.approved_plan_id
  ),
  reviews_left as (
    select
      count(reviews.id)::bigint as review_count,
      round(avg(reviews.rating)::numeric, 2) as average_rating
    from current_user_id
    left join public.tour_reviews as reviews
      on reviews.user_id = current_user_id.id
  ),
  owned_tour_reviews as (
    select
      count(reviews.id)::bigint as review_count,
      round(avg(reviews.rating)::numeric, 2) as average_rating
    from current_user_id
    left join public.tours on tours.owner_id = current_user_id.id
    left join public.tour_reviews as reviews on reviews.tour_id = tours.id
  ),
  credits as (
    select coalesce(sum(transactions.delta), 0)::bigint as balance
    from current_user_id
    left join public.credit_transactions as transactions
      on transactions.user_id = current_user_id.id
  )
  select jsonb_build_object(
    'credits', credits.balance,
    'created', jsonb_build_object(
      'ready_tours', created_tours.ready_count,
      'public_tours', created_tours.public_count,
      'distance_meters', created_tours.distance_meters,
      'duration_seconds', created_tours.duration_seconds
    ),
    'completed', jsonb_build_object(
      'tours', completed_tours.completion_count,
      'distance_meters', completed_tours.distance_meters,
      'duration_seconds', completed_tours.duration_seconds
    ),
    'community', jsonb_build_object(
      'completions', community_walks.completion_count,
      'unique_walkers', community_walks.unique_walkers,
      'distance_meters', community_walks.distance_meters,
      'duration_seconds', community_walks.duration_seconds
    ),
    'reviews', jsonb_build_object(
      'left_count', reviews_left.review_count,
      'left_average', reviews_left.average_rating,
      'owned_count', owned_tour_reviews.review_count,
      'owned_average', owned_tour_reviews.average_rating
    )
  )
  from created_tours, completed_tours, community_walks,
       reviews_left, owned_tour_reviews, credits;
$$;

revoke all on function public.get_profile_stats() from public;
grant execute on function public.get_profile_stats() to authenticated;

create function public.mark_review_tour_completed()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.tour_completions (tour_id, user_id)
  values (new.tour_id, new.user_id)
  on conflict (tour_id, user_id) do nothing;
  return new;
end;
$$;

create trigger tour_reviews_mark_completed
after insert or update on public.tour_reviews
for each row execute function public.mark_review_tour_completed();

revoke all on function public.mark_review_tour_completed() from public;
grant execute on function public.mark_review_tour_completed() to service_role;
