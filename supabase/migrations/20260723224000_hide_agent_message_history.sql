revoke select on public.tour_plan_revisions from authenticated;

grant select (
  id,
  tour_id,
  revision,
  checkpoint_research,
  route_plan,
  parent_plan_id,
  feedback,
  created_at
) on public.tour_plan_revisions to authenticated;
