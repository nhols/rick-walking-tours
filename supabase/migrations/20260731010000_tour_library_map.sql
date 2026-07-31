alter table public.tours
  add column start_lat double precision,
  add column start_lon double precision,
  add constraint tours_start_coordinates_pair check (
    (start_lat is null and start_lon is null)
    or
    (
      start_lat is not null
      and start_lon is not null
      and
      start_lat between -90 and 90
      and start_lon between -180 and 180
    )
  );

update public.tours as tours
set
  start_lat = (plans.payload #>> '{checkpoints,0,lat}')::double precision,
  start_lon = (plans.payload #>> '{checkpoints,0,lon}')::double precision
from public.tour_plan_revisions as plans
where plans.id = tours.approved_plan_id
  and jsonb_typeof(plans.payload #> '{checkpoints,0,lat}') = 'number'
  and jsonb_typeof(plans.payload #> '{checkpoints,0,lon}') = 'number';

create function public.set_tour_start_coordinates()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_payload jsonb;
begin
  if new.approved_plan_id is null then
    new.start_lat := null;
    new.start_lon := null;
    return new;
  end if;

  select payload into v_payload
  from public.tour_plan_revisions
  where id = new.approved_plan_id;

  if jsonb_typeof(v_payload #> '{checkpoints,0,lat}') = 'number'
    and jsonb_typeof(v_payload #> '{checkpoints,0,lon}') = 'number' then
    new.start_lat := (v_payload #>> '{checkpoints,0,lat}')::double precision;
    new.start_lon := (v_payload #>> '{checkpoints,0,lon}')::double precision;
  else
    new.start_lat := null;
    new.start_lon := null;
  end if;

  return new;
end;
$$;

create trigger tours_set_start_coordinates
before update of approved_plan_id on public.tours
for each row execute function public.set_tour_start_coordinates();

revoke all on function public.set_tour_start_coordinates() from public;
grant execute on function public.set_tour_start_coordinates() to service_role;
