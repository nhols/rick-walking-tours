import unittest

from tour_gen.backend.models import TourPlanPayload
from tour_gen.geo.routes.google_maps import _parse_google_maps_response
from tour_gen.geo.routes.mapbox import _parse_mapbox_response


class RouteModelTest(unittest.TestCase):
    def test_older_plan_payload_remains_valid(self) -> None:
        payload = TourPlanPayload.model_validate(
            {
                "narrative_arc": "Past to present",
                "checkpoints": [],
            }
        )

        self.assertIsNone(payload.route)
        self.assertIsNone(payload.response_to_user)


class MapboxRouteTest(unittest.TestCase):
    def test_response_is_normalized_with_leg_summaries(self) -> None:
        route = _parse_mapbox_response(
            {
                "code": "Ok",
                "routes": [
                    {
                        "distance": 1250.5,
                        "duration": 932.4,
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [-3.19, 55.94],
                                [-3.18, 55.95],
                                [-3.17, 55.96],
                            ],
                        },
                        "legs": [
                            {"distance": 600.0, "duration": 440.0},
                            {"distance": 650.5, "duration": 492.4},
                        ],
                    }
                ],
                "waypoints": [
                    {"location": [-3.19, 55.94]},
                    {"location": [-3.18, 55.95]},
                    {"location": [-3.17, 55.96]},
                ],
            }
        )

        self.assertEqual(route.provider, "mapbox")
        self.assertEqual(route.distance_meters, 1250.5)
        self.assertEqual(route.duration_seconds, 932.4)
        self.assertEqual(len(route.legs), 2)
        start = route.legs[0].start
        end = route.legs[1].end
        assert start is not None and end is not None
        self.assertEqual(start.lon, -3.19)
        self.assertEqual(end.lat, 55.96)


class GoogleMapsRouteTest(unittest.TestCase):
    def test_response_is_normalized_with_warnings(self) -> None:
        route = _parse_google_maps_response(
            {
                "routes": [
                    {
                        "distanceMeters": 1251,
                        "duration": "932.4s",
                        "polyline": {
                            "geoJsonLinestring": {
                                "type": "LineString",
                                "coordinates": [
                                    [-3.19, 55.94],
                                    [-3.18, 55.95],
                                    [-3.17, 55.96],
                                ],
                            }
                        },
                        "legs": [
                            {
                                "distanceMeters": 600,
                                "duration": "440s",
                                "startLocation": {
                                    "latLng": {
                                        "latitude": 55.94,
                                        "longitude": -3.19,
                                    }
                                },
                                "endLocation": {
                                    "latLng": {
                                        "latitude": 55.95,
                                        "longitude": -3.18,
                                    }
                                },
                            },
                            {
                                "distanceMeters": 651,
                                "duration": "492.4s",
                                "startLocation": {
                                    "latLng": {
                                        "latitude": 55.95,
                                        "longitude": -3.18,
                                    }
                                },
                                "endLocation": {
                                    "latLng": {
                                        "latitude": 55.96,
                                        "longitude": -3.17,
                                    }
                                },
                            },
                        ],
                        "warnings": ["Walking directions may be incomplete"],
                    }
                ]
            }
        )

        self.assertEqual(route.provider, "google_maps")
        self.assertEqual(route.duration_seconds, 932.4)
        self.assertEqual(len(route.legs), 2)
        self.assertEqual(route.warnings, ["Walking directions may be incomplete"])
        end = route.legs[1].end
        assert end is not None
        self.assertEqual(end.lon, -3.17)


if __name__ == "__main__":
    unittest.main()
