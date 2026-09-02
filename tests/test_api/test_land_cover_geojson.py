from app.dependencies import get_worldcover_service
from app.main import app


class FakeWorldCoverService:
    async def get_land_cover_for_geojson(self, geojson):
        if geojson["type"] == "Point":
            return {"class": 10}
        return {"10": 0.5, "20": 0.5}


async def test_geojson_api_returns_typed_point_and_fraction_responses(context):
    user = await context.create_user("user@example.com")
    app.dependency_overrides[get_worldcover_service] = FakeWorldCoverService
    headers = {"Authorization": f"Bearer {user.bearer_token}"}

    point = await context.client.post(
        "/api/land-cover-geojson",
        files={
            "geojson_file": (
                "point.geojson",
                b'{"type":"Point","coordinates":[0.5,5.5]}',
                "application/geo+json",
            )
        },
        headers=headers,
    )
    polygon = await context.client.post(
        "/api/land-cover-geojson",
        files={
            "geojson_file": (
                "polygon.geojson",
                b'{"type":"Polygon","coordinates":[[[0,1],[1,1],[1,0],[0,1]]]}',
                "application/geo+json",
            )
        },
        headers=headers,
    )

    assert point.status_code == 200
    assert point.json() == {"class": 10}
    assert polygon.status_code == 200
    assert polygon.json() == {"10": 0.5, "20": 0.5}


async def test_invalid_geojson_uses_validation_error_without_internal_details(context):
    user = await context.create_user("user@example.com")
    response = await context.client.post(
        "/api/land-cover-geojson",
        files={"geojson_file": ("bad.geojson", b"not json", "application/geo+json")},
        headers={"Authorization": f"Bearer {user.bearer_token}"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "GeoJSON file is not valid JSON"}
