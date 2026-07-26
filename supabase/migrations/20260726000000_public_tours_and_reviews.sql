alter table public.tours
  add column is_public boolean not null default false;

create table public.tour_reviews (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  rating smallint not null check (rating between 1 and 5),
  body text not null check (
    char_length(btrim(body)) between 1 and 1000
  ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tour_id, user_id)
);

create index tour_reviews_tour_created_idx
  on public.tour_reviews(tour_id, created_at desc);

create trigger tour_reviews_set_updated_at
before update on public.tour_reviews
for each row execute function public.set_updated_at();

alter table public.tour_reviews enable row level security;

drop policy tours_select_own on public.tours;
create policy tours_select_visible on public.tours
for select to authenticated using (
  owner_id = auth.uid() or (is_public and status = 'ready')
);

create policy tours_update_visibility_own on public.tours
for update to authenticated
using (owner_id = auth.uid())
with check (
  owner_id = auth.uid() and (not is_public or status = 'ready')
);

drop policy plans_select_own on public.tour_plan_revisions;
create policy plans_select_visible on public.tour_plan_revisions
for select to authenticated using (
  exists (
    select 1 from public.tours
    where tours.id = tour_plan_revisions.tour_id
      and (
        tours.owner_id = auth.uid()
        or (
          tours.is_public
          and tours.status = 'ready'
          and tours.approved_plan_id = tour_plan_revisions.id
        )
      )
  )
);

drop policy outputs_select_own on public.tour_outputs;
create policy outputs_select_visible on public.tour_outputs
for select to authenticated using (
  exists (
    select 1 from public.tours
    where tours.id = tour_outputs.tour_id
      and (
        tours.owner_id = auth.uid()
        or (
          tours.is_public
          and tours.status = 'ready'
          and tours.approved_plan_id = tour_outputs.plan_id
        )
      )
  )
);

drop policy tour_audio_select_own on storage.objects;
create policy tour_audio_select_visible on storage.objects
for select to authenticated using (
  bucket_id = 'tour-audio'
  and (
    (storage.foldername(name))[1] = auth.uid()::text
    or exists (
      select 1 from public.tours
      where tours.id::text = (storage.foldername(name))[2]
        and tours.is_public
        and tours.status = 'ready'
    )
  )
);

create policy tour_reviews_select_visible on public.tour_reviews
for select to authenticated using (
  exists (
    select 1 from public.tours
    where tours.id = tour_reviews.tour_id
      and tours.status = 'ready'
      and (tours.owner_id = auth.uid() or tours.is_public)
  )
);

create policy tour_reviews_insert_own on public.tour_reviews
for insert to authenticated with check (
  user_id = auth.uid()
  and exists (
    select 1 from public.tours
    where tours.id = tour_reviews.tour_id
      and tours.status = 'ready'
      and (tours.owner_id = auth.uid() or tours.is_public)
  )
);

create policy tour_reviews_update_own on public.tour_reviews
for update to authenticated
using (user_id = auth.uid())
with check (
  user_id = auth.uid()
  and exists (
    select 1 from public.tours
    where tours.id = tour_reviews.tour_id
      and tours.status = 'ready'
      and (tours.owner_id = auth.uid() or tours.is_public)
  )
);

create policy tour_reviews_delete_own on public.tour_reviews
for delete to authenticated using (user_id = auth.uid());

grant select on public.tour_reviews to authenticated;
grant insert (tour_id, user_id, rating, body) on public.tour_reviews to authenticated;
grant update (rating, body) on public.tour_reviews to authenticated;
grant delete on public.tour_reviews to authenticated;
grant update (is_public) on public.tours to authenticated;
grant all on public.tour_reviews to service_role;
