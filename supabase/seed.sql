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
  '{}',
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

-- Local-only reviewer login: reviewer@rick.local / password123
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
  '00000000-0000-0000-0000-000000000002',
  'authenticated',
  'authenticated',
  'reviewer@rick.local',
  extensions.crypt('password123', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}',
  '{}',
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
  '00000000-0000-0000-0000-000000000102',
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-000000000002',
  '{"sub":"00000000-0000-0000-0000-000000000002","email":"reviewer@rick.local"}',
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
  id, owner_id, status, input
) values (
  '00000000-0000-0000-0000-000000000301',
  '00000000-0000-0000-0000-000000000001',
  'awaiting_review',
  '{
    "location": "Edinburgh",
    "request": "A short walk through the Old Town''s literary history",
    "min_stops": 2,
    "max_stops": 10,
    "max_checkpoint_distance_km": 10,
    "voice": "Kore",
    "audio_format": "wav"
  }'
) on conflict (id) do nothing;

insert into public.tour_status_events (
  id, tour_id, status
) values (
  '00000000-0000-0000-0000-000000000701',
  '00000000-0000-0000-0000-000000000301',
  'awaiting_review'
) on conflict (id) do nothing;

insert into public.tour_plan_revisions (
  id, tour_id, revision, payload
) values (
  '00000000-0000-0000-0000-000000000401',
  '00000000-0000-0000-0000-000000000301',
  1,
  '{
    "narrative_arc": "From medieval closes to the writers who transformed the city.",
    "checkpoints": [
      {
        "id": "00000000-0000-0000-0000-000000000501",
        "position": 1,
        "title": "Writers'' Museum",
        "description": "A compact introduction to three major Scottish writers.",
        "route_reasoning": "Begin with the writers and their surviving objects.",
        "distance_tool_place_name": "The Writers'' Museum, Edinburgh",
        "lat": 55.9496,
        "lon": -3.1938,
        "formatted_address": "Lady Stair''s Close, Edinburgh"
      },
      {
        "id": "00000000-0000-0000-0000-000000000502",
        "position": 2,
        "title": "Scott Monument",
        "description": "A dramatic memorial to Walter Scott in the heart of the city.",
        "route_reasoning": "Finish with the city-scale legacy of Walter Scott.",
        "distance_tool_place_name": "Scott Monument, Edinburgh",
        "lat": 55.9524,
        "lon": -3.1933,
        "formatted_address": "East Princes Street Gardens, Edinburgh"
      }
    ]
  }'
) on conflict (id) do nothing;
