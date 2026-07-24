alter table public.tour_plan_revisions
  add column parent_plan_id uuid references public.tour_plan_revisions(id),
  add column feedback text,
  add column checkpoint_agent_messages jsonb not null default '[]'::jsonb;

create index tour_plan_revisions_parent_idx
  on public.tour_plan_revisions(parent_plan_id);

alter table public.tour_plan_revisions
  add constraint tour_plan_revisions_feedback_shape_check check (
    (revision = 1 and parent_plan_id is null and feedback is null)
    or
    (revision > 1 and parent_plan_id is not null and nullif(btrim(feedback), '') is not null)
  ),
  add constraint tour_plan_revisions_messages_array_check check (
    jsonb_typeof(checkpoint_agent_messages) = 'array'
  );

drop function public.persist_tour_plan(uuid, jsonb, jsonb, jsonb);

create function public.persist_tour_plan(
  p_tour_id uuid,
  p_checkpoint_research jsonb,
  p_route_plan jsonb,
  p_checkpoints jsonb,
  p_parent_plan_id uuid,
  p_feedback text,
  p_checkpoint_agent_messages jsonb
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
  v_current_plan_id uuid;
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
  if jsonb_typeof(p_checkpoint_agent_messages) is distinct from 'array' then
    raise exception 'Checkpoint agent messages must be a JSON array';
  end if;

  v_revision := v_tour.current_plan_revision + 1;
  if v_revision = 1 then
    if p_parent_plan_id is not null or p_feedback is not null then
      raise exception 'The initial plan cannot have feedback or a parent plan';
    end if;
  else
    select id into v_current_plan_id
    from public.tour_plan_revisions
    where tour_id = p_tour_id
    order by revision desc
    limit 1;

    if p_parent_plan_id is distinct from v_current_plan_id then
      raise exception 'Feedback must target the current tour plan';
    end if;
    if nullif(btrim(p_feedback), '') is null then
      raise exception 'Feedback is required for a revised plan';
    end if;
    if v_tour.current_plan_revision - 1 >= 3 then
      raise exception 'A tour can have at most 3 feedback rounds';
    end if;
  end if;

  insert into public.tour_plan_revisions (
    tour_id,
    revision,
    checkpoint_research,
    route_plan,
    parent_plan_id,
    feedback,
    checkpoint_agent_messages
  ) values (
    p_tour_id,
    v_revision,
    p_checkpoint_research,
    p_route_plan,
    p_parent_plan_id,
    p_feedback,
    p_checkpoint_agent_messages
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

revoke all on function public.persist_tour_plan(
  uuid,
  jsonb,
  jsonb,
  jsonb,
  uuid,
  text,
  jsonb
) from public;

grant execute on function public.persist_tour_plan(
  uuid,
  jsonb,
  jsonb,
  jsonb,
  uuid,
  text,
  jsonb
) to service_role;
