create table public.tour_assistant_turns (
  id uuid primary key default gen_random_uuid(),
  tour_id uuid not null references public.tours(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  thread_id uuid not null,
  turn integer not null check (turn > 0),
  input jsonb not null check (jsonb_typeof(input) = 'object'),
  output jsonb not null check (jsonb_typeof(output) = 'object'),
  new_messages jsonb not null check (jsonb_typeof(new_messages) = 'array'),
  created_at timestamptz not null default now(),
  unique (tour_id, user_id, thread_id, turn)
);

create index tour_assistant_turns_user_tour_idx
  on public.tour_assistant_turns(user_id, tour_id, created_at desc);

alter table public.tour_assistant_turns enable row level security;

create policy tour_assistant_turns_select_own
on public.tour_assistant_turns
for select to authenticated
using (user_id = auth.uid());

revoke all on public.tour_assistant_turns from anon, authenticated;
grant select on public.tour_assistant_turns to authenticated;
grant all on public.tour_assistant_turns to service_role;
