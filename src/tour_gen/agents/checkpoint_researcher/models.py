from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from tour_gen.geo.distance_matrix import GeocodedPlace
from tour_gen.geo.geoencode import GeocodeResult, Geocoder


class CheckpointProposal(BaseModel):
    title: str = Field(min_length=1)
    brief_description: str = Field(min_length=1, max_length=240)
    route_reasoning: str = Field(min_length=1, max_length=240)
    distance_tool_place_name: str = Field(min_length=1)


class CheckpointResearchOutput(BaseModel):
    ordered_checkpoints: list[CheckpointProposal] = Field(min_length=1)
    narrative_arc: str = Field(min_length=1, max_length=600)
    response_to_user: str = Field(min_length=1, max_length=600)


@dataclass
class CheckpointResearchArtifacts:
    checked_shortlists: set[frozenset[str]] = field(default_factory=set)
    geocoded_places: dict[str, GeocodedPlace] = field(default_factory=dict)


@dataclass
class CheckpointResearchDeps:
    location: str
    geocoder: Geocoder
    min_stops: int = 2
    max_stops: int = 10
    max_checkpoint_distance_km: float = 10.0
    artifacts: CheckpointResearchArtifacts = field(
        default_factory=CheckpointResearchArtifacts
    )
    location_geocode: GeocodeResult | None = None
