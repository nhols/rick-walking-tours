-- Local-only login: demo@rick.local / password123
insert into auth.users (
  instance_id,
  id,
  aud,
  role,
  email,
  encrypted_password,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  created_at,
  updated_at,
  confirmation_token,
  email_change,
  email_change_token_new,
  recovery_token
) values (
  '00000000-0000-0000-0000-000000000000',
  '00000000-0000-0000-0000-000000000001',
  'authenticated',
  'authenticated',
  'demo@rick.local',
  extensions.crypt('password123', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}',
  '{"display_name":"Demo Walker"}',
  now(),
  now(),
  '',
  '',
  '',
  ''
) on conflict (id) do nothing;

insert into auth.identities (
  id,
  user_id,
  provider_id,
  identity_data,
  provider,
  last_sign_in_at,
  created_at,
  updated_at
) values (
  '00000000-0000-0000-0000-000000000101',
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  '{"sub":"00000000-0000-0000-0000-000000000001","email":"demo@rick.local"}',
  'email',
  now(),
  now(),
  now()
) on conflict (provider_id, provider) do nothing;

insert into public.credit_transactions (
  id, user_id, delta, reason, idempotency_key
) values (
  '00000000-0000-0000-0000-000000000201',
  '00000000-0000-0000-0000-000000000001',
  3,
  'local_seed',
  'local-seed-demo-credits'
) on conflict (idempotency_key) do nothing;

insert into public.tours (
  id,
  owner_id,
  location,
  request,
  status,
  narrative_arc,
  current_plan_revision,
  progress_message,
  progress_current,
  progress_total
) values (
  '00000000-0000-0000-0000-000000000301',
  '00000000-0000-0000-0000-000000000001',
  'Edinburgh',
  'A short walk through the Old Town''s literary history',
  'awaiting_review',
  'From medieval closes to the writers who transformed the city.',
  1,
  'Plan ready for review',
  2,
  2
) on conflict (id) do nothing;

insert into public.tour_plan_revisions (
  id, tour_id, revision, checkpoint_research, route_plan
) values (
  '00000000-0000-0000-0000-000000000401',
  '00000000-0000-0000-0000-000000000301',
  1,
  '{"proposals":[{"title":"Writers'' Museum","brief_description":"A compact introduction to three major Scottish writers.","distance_tool_place_name":"The Writers'' Museum, Edinburgh"},{"title":"Scott Monument","brief_description":"A dramatic memorial to Walter Scott in the heart of the city.","distance_tool_place_name":"Scott Monument, Edinburgh"}]}',
  '{"ordered_checkpoints":[{"title":"Writers'' Museum","reasoning":"Begin with the writers and their surviving objects."},{"title":"Scott Monument","reasoning":"Finish with the city-scale legacy of Walter Scott."}],"narrative_arc":"From medieval closes to the writers who transformed the city."}'
) on conflict (id) do nothing;

insert into public.tour_checkpoints (
  id,
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
) values
  (
    '00000000-0000-0000-0000-000000000501',
    '00000000-0000-0000-0000-000000000301',
    '00000000-0000-0000-0000-000000000401',
    1,
    'Writers'' Museum',
    'A compact introduction to three major Scottish writers.',
    'Begin with the writers and their surviving objects.',
    'The Writers'' Museum, Edinburgh',
    55.9496,
    -3.1938,
    'Lady Stair''s Close, Edinburgh'
  ),
  (
    '00000000-0000-0000-0000-000000000502',
    '00000000-0000-0000-0000-000000000301',
    '00000000-0000-0000-0000-000000000401',
    2,
    'Scott Monument',
    'A dramatic memorial to Walter Scott in the heart of the city.',
    'Finish with the city-scale legacy of Walter Scott.',
    'Scott Monument, Edinburgh',
    55.9524,
    -3.1933,
    'East Princes Street Gardens, Edinburgh'
  )
on conflict (id) do nothing;
