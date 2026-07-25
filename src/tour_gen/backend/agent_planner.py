from typing import Any
from uuid import uuid4

from tour_gen import pipeline
from tour_gen.backend.models import TourCheckpoint, TourInput, TourPlanPayload
from tour_gen.backend.ports import GeneratedPlan
from tour_gen.geo.geoencode import Geocoder


class AgentTourPlanner:
    def __init__(self, geocoder: Geocoder) -> None:
        self.geocoder = geocoder

    async def plan(
        self,
        input: TourInput,
        prompt: str,
        history: list[dict[str, Any]],
    ) -> GeneratedPlan:
        run = await pipeline.research_checkpoints(
            prompt=prompt,
            location=input.location,
            geocoder=self.geocoder,
            min_stops=input.min_stops,
            max_stops=input.max_stops,
            max_checkpoint_distance_km=input.max_checkpoint_distance_km,
            message_history=history or None,
        )
        titles = [item.title for item in run.output.ordered_checkpoints]
        if len(titles) != len(set(titles)):
            raise ValueError("Checkpoint titles must be unique")
        points = {item.place_name: item for item in run.coordinates}
        checkpoints: list[TourCheckpoint] = []
        for position, checkpoint in enumerate(run.output.ordered_checkpoints, start=1):
            point = points.get(checkpoint.distance_tool_place_name)
            if point is None:
                raise ValueError(
                    f"Missing coordinates for {checkpoint.distance_tool_place_name}"
                )
            checkpoints.append(
                TourCheckpoint(
                    id=uuid4(),
                    position=position,
                    title=checkpoint.title,
                    description=checkpoint.brief_description,
                    route_reasoning=checkpoint.route_reasoning,
                    distance_tool_place_name=checkpoint.distance_tool_place_name,
                    lat=point.lat,
                    lon=point.lon,
                    formatted_address=point.formatted_address,
                )
            )
        return GeneratedPlan(
            payload=TourPlanPayload(
                narrative_arc=run.output.narrative_arc,
                checkpoints=checkpoints,
            ),
            new_messages=run.new_agent_messages,
        )
