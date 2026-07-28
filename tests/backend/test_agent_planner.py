import unittest
from unittest.mock import AsyncMock, Mock, patch

from tour_gen.agents.checkpoint_researcher import (
    CheckpointProposal,
    CheckpointResearchOutput,
)
from tour_gen.backend.agent_planner import AgentTourPlanner
from tour_gen.backend.models import TourInput
from tour_gen.geo.models import GeoJsonLineString
from tour_gen.geo.routes import WalkingRoute
from tour_gen.pipeline import CheckpointCoordinates, CheckpointResearchRun


CHECKPOINTS = [
    CheckpointProposal(
        title="First stop",
        brief_description="First description",
        route_reasoning="Start here",
        distance_tool_place_name="First place",
    ),
    CheckpointProposal(
        title="Second stop",
        brief_description="Second description",
        route_reasoning="Finish here",
        distance_tool_place_name="Second place",
    ),
]
RESEARCH_RUN = CheckpointResearchRun(
    output=CheckpointResearchOutput(
        narrative_arc="Past to present",
        ordered_checkpoints=CHECKPOINTS,
    ),
    coordinates=[
        CheckpointCoordinates(place_name="First place", lat=55.94, lon=-3.19),
        CheckpointCoordinates(place_name="Second place", lat=55.95, lon=-3.18),
    ],
    new_agent_messages=[],
)
ROUTE = WalkingRoute(
    provider="mapbox",
    geometry=GeoJsonLineString(
        coordinates=[(-3.19, 55.94), (-3.18, 55.95)]
    ),
    distance_meters=1_200,
    duration_seconds=900,
)


class AgentTourPlannerRouteTest(unittest.IsolatedAsyncioTestCase):
    @patch(
        "tour_gen.backend.agent_planner.pipeline.research_checkpoints",
        new_callable=AsyncMock,
    )
    async def test_route_is_stored_using_checkpoint_order(
        self,
        research_checkpoints: AsyncMock,
    ) -> None:
        research_checkpoints.return_value = RESEARCH_RUN
        router = Mock()
        router.walking_route = AsyncMock(return_value=ROUTE)
        planner = AgentTourPlanner(Mock(), router)

        generated = await planner.plan(
            TourInput(location="Edinburgh", request="History"),
            "History",
            [],
        )

        self.assertEqual(generated.payload.route, ROUTE)
        route_call = router.walking_route.await_args
        assert route_call is not None
        waypoints = route_call.args[0]
        self.assertEqual(
            [(point.lat, point.lon) for point in waypoints],
            [(55.94, -3.19), (55.95, -3.18)],
        )

    @patch(
        "tour_gen.backend.agent_planner.pipeline.research_checkpoints",
        new_callable=AsyncMock,
    )
    async def test_route_failure_does_not_fail_plan(
        self,
        research_checkpoints: AsyncMock,
    ) -> None:
        research_checkpoints.return_value = RESEARCH_RUN
        router = Mock()
        router.walking_route = AsyncMock(side_effect=RuntimeError("router offline"))
        planner = AgentTourPlanner(Mock(), router)

        generated = await planner.plan(
            TourInput(location="Edinburgh", request="History"),
            "History",
            [],
        )

        self.assertIsNone(generated.payload.route)


if __name__ == "__main__":
    unittest.main()
