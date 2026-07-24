create type public.tour_status as enum (
  'researching',
  'planning_route',
  'awaiting_review',
  'writing_chapters',
  'generating_audio',
  'ready',
  'failed'
);

create type public.chapter_status as enum ('written', 'ready');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.tours (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  location text not null,
  request text not null,
  status public.tour_status not null default 'researching',
  title text,
  narrative_arc text,
  voice text not null default 'Kore',
  voice_style text,
  tts_model text,
  audio_format text not null default 'wav',
  tts_style jsonb,
  current_plan_revision integer not null default 0,
  approved_plan_id uuid,
  progress_message text,
  progress_current integer,
  progress_total integer,
  error_message text,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index tours_owner_created_idx on public.tours(owner_id, created_at desc);
create index tours_status_idx on public.tours(status);

create table public.tour_plan_revisions (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  revision integer not null check (revision > 0),
  checkpoint_research jsonb not null,
  route_plan jsonb not null,
  created_at timestamptz not null default now(),
  unique (tour_id, revision)
);

alter table public.tours
  add constraint tours_approved_plan_fk
  foreign key (approved_plan_id)
  references public.tour_plan_revisions(id);

create table public.tour_checkpoints (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  plan_id uuid not null references public.tour_plan_revisions(id) on delete cascade,
  position integer not null check (position > 0),
  title text not null,
  description text not null,
  route_reasoning text not null,
  distance_tool_place_name text not null,
  lat double precision not null check (lat between -90 and 90),
  lon double precision not null check (lon between -180 and 180),
  formatted_address text,
  unique (plan_id, position)
);

create index tour_checkpoints_tour_idx on public.tour_checkpoints(tour_id);

create table public.tour_chapters (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  plan_id uuid not null references public.tour_plan_revisions(id) on delete cascade,
  checkpoint_id uuid not null references public.tour_checkpoints(id),
  position integer not null check (position > 0),
  title text not null,
  narration text not null,
  status public.chapter_status not null default 'written',
  audio_path text,
  media_type text,
  audio_format text,
  byte_count bigint,
  voice text,
  model text,
  duration_seconds double precision,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (plan_id, position)
);

create index tour_chapters_tour_idx on public.tour_chapters(tour_id);

create table public.credit_transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  delta integer not null check (delta <> 0),
  reason text not null,
  tour_id uuid references public.tours(id),
  idempotency_key text not null unique,
  created_at timestamptz not null default now()
);

create index credit_transactions_user_idx
  on public.credit_transactions(user_id, created_at desc);

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

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create trigger tours_set_updated_at
before update on public.tours
for each row execute function public.set_updated_at();

create trigger tour_chapters_set_updated_at
before update on public.tour_chapters
for each row execute function public.set_updated_at();

create function public.create_profile_for_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'display_name', split_part(new.email, '@', 1)))
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger create_profile_after_signup
after insert on auth.users
for each row execute function public.create_profile_for_user();

create function public.persist_tour_plan(
  p_tour_id uuid,
  p_checkpoint_research jsonb,
  p_route_plan jsonb,
  p_checkpoints jsonb
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_tour public.tours;
  v_plan public.tour_plan_revisions;
  v_checkpoint jsonb;
  v_revision integer;
begin
  select * into v_tour
  from public.tours
  where id = p_tour_id
  for update;

  if not found then
    raise exception 'Tour not found';
  end if;
  if v_tour.status not in ('researching', 'planning_route') then
    raise exception 'Tour cannot accept a plan while %', v_tour.status;
  end if;

  v_revision := v_tour.current_plan_revision + 1;
  insert into public.tour_plan_revisions (
    tour_id, revision, checkpoint_research, route_plan
  ) values (
    p_tour_id, v_revision, p_checkpoint_research, p_route_plan
  ) returning * into v_plan;

  for v_checkpoint in select value from jsonb_array_elements(p_checkpoints)
  loop
    insert into public.tour_checkpoints (
      tour_id,
      plan_id,
      position,
      title,
      description,
      route_reasoning,
      distance_tool_place_name,
      lat,
      lon,
      formatted_address
    ) values (
      p_tour_id,
      v_plan.id,
      (v_checkpoint ->> 'position')::integer,
      v_checkpoint ->> 'title',
      v_checkpoint ->> 'description',
      v_checkpoint ->> 'route_reasoning',
      v_checkpoint ->> 'distance_tool_place_name',
      (v_checkpoint ->> 'lat')::double precision,
      (v_checkpoint ->> 'lon')::double precision,
      v_checkpoint ->> 'formatted_address'
    );
  end loop;

  update public.tours set
    current_plan_revision = v_revision,
    narrative_arc = p_route_plan ->> 'narrative_arc',
    status = 'awaiting_review',
    progress_message = 'Plan ready for review',
    progress_current = jsonb_array_length(p_checkpoints),
    progress_total = jsonb_array_length(p_checkpoints),
    error_message = null
  where id = p_tour_id;

  return v_plan.id;
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
    where id = p_plan_id and tour_id = p_tour_id
  ) then
    raise exception 'The approved plan is not the current tour plan';
  end if;
  if v_tour.status = 'ready' and v_tour.approved_plan_id = p_plan_id then
    return false;
  end if;
  if v_tour.status <> 'awaiting_review' then
    raise exception 'Tour cannot be approved while %', v_tour.status;
  end if;

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

create function public.persist_written_chapters(
  p_tour_id uuid,
  p_plan_id uuid,
  p_tour_title text,
  p_tts_style jsonb,
  p_chapters jsonb
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_chapter jsonb;
begin
  if not exists (
    select 1 from public.tours
    where id = p_tour_id and approved_plan_id = p_plan_id
  ) then
    raise exception 'Tour plan is not approved';
  end if;

  for v_chapter in select value from jsonb_array_elements(p_chapters)
  loop
    insert into public.tour_chapters (
      tour_id, plan_id, checkpoint_id, position, title, narration, status
    ) values (
      p_tour_id,
      p_plan_id,
      (v_chapter ->> 'checkpoint_id')::uuid,
      (v_chapter ->> 'position')::integer,
      v_chapter ->> 'title',
      v_chapter ->> 'narration',
      'written'
    )
    on conflict (plan_id, position) do update set
      checkpoint_id = excluded.checkpoint_id,
      title = excluded.title,
      narration = excluded.narration,
      status = 'written';
  end loop;

  update public.tours set title = p_tour_title, tts_style = p_tts_style
  where id = p_tour_id;
end;
$$;

create function public.finalize_tour_audio(p_tour_id uuid, p_audio jsonb)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_audio jsonb;
  v_chapter_count integer;
begin
  select count(*) into v_chapter_count
  from public.tour_chapters
  where tour_id = p_tour_id;

  if v_chapter_count = 0 or v_chapter_count <> jsonb_array_length(p_audio) then
    raise exception 'Audio metadata does not match chapter count';
  end if;

  for v_audio in select value from jsonb_array_elements(p_audio)
  loop
    update public.tour_chapters set
      audio_path = v_audio ->> 'audio_path',
      media_type = v_audio ->> 'media_type',
      audio_format = v_audio ->> 'audio_format',
      byte_count = (v_audio ->> 'byte_count')::bigint,
      voice = v_audio ->> 'voice',
      model = v_audio ->> 'model',
      duration_seconds = (v_audio ->> 'duration_seconds')::double precision,
      status = 'ready'
    where id = (v_audio ->> 'chapter_id')::uuid and tour_id = p_tour_id;

    if not found then
      raise exception 'Chapter not found while finalizing audio';
    end if;
  end loop;

  update public.tours set
    status = 'ready',
    progress_message = 'Tour ready',
    progress_current = v_chapter_count,
    progress_total = v_chapter_count,
    error_message = null
  where id = p_tour_id;
end;
$$;

alter table public.profiles enable row level security;
alter table public.tours enable row level security;
alter table public.tour_plan_revisions enable row level security;
alter table public.tour_checkpoints enable row level security;
alter table public.tour_chapters enable row level security;
alter table public.credit_transactions enable row level security;

create policy profiles_select_own on public.profiles
for select to authenticated using (id = auth.uid());

create policy profiles_update_own on public.profiles
for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

create policy tours_select_own on public.tours
for select to authenticated using (owner_id = auth.uid());

create policy plans_select_own on public.tour_plan_revisions
for select to authenticated using (
  exists (
    select 1 from public.tours
    where tours.id = tour_plan_revisions.tour_id
      and tours.owner_id = auth.uid()
  )
);

create policy checkpoints_select_own on public.tour_checkpoints
for select to authenticated using (
  exists (
    select 1 from public.tours
    where tours.id = tour_checkpoints.tour_id
      and tours.owner_id = auth.uid()
  )
);

create policy chapters_select_own on public.tour_chapters
for select to authenticated using (
  exists (
    select 1 from public.tours
    where tours.id = tour_chapters.tour_id
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

revoke all on public.profiles,
  public.tours,
  public.tour_plan_revisions,
  public.tour_checkpoints,
  public.tour_chapters,
  public.credit_transactions
from anon, authenticated;

grant select on public.profiles,
  public.tours,
  public.tour_plan_revisions,
  public.tour_checkpoints,
  public.tour_chapters,
  public.credit_transactions
to authenticated;

grant update (display_name) on public.profiles to authenticated;

grant all on public.profiles,
  public.tours,
  public.tour_plan_revisions,
  public.tour_checkpoints,
  public.tour_chapters,
  public.credit_transactions
to service_role;

revoke all on function public.persist_tour_plan(uuid, jsonb, jsonb, jsonb) from public;
revoke all on function public.begin_tour_production(uuid, uuid) from public;
revoke all on function public.persist_written_chapters(uuid, uuid, text, jsonb, jsonb) from public;
revoke all on function public.finalize_tour_audio(uuid, jsonb) from public;

grant execute on function public.persist_tour_plan(uuid, jsonb, jsonb, jsonb) to service_role;
grant execute on function public.begin_tour_production(uuid, uuid) to service_role;
grant execute on function public.persist_written_chapters(uuid, uuid, text, jsonb, jsonb) to service_role;
grant execute on function public.finalize_tour_audio(uuid, jsonb) to service_role;
