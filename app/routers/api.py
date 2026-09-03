import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.dependencies import WorldCoverServiceDependency, get_current_active_user
from app.schemas.schemas import LandCoverFractionsResponse, LandCoverResponse
from app.services.worldcover import GeoJSONNoTileCoverageError

router = APIRouter(
    prefix="/api",
    tags=["API"],
    dependencies=[Depends(get_current_active_user)],
)


@router.get("/land-cover", response_model=LandCoverResponse)
async def get_land_cover(
    service: WorldCoverServiceDependency,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
) -> LandCoverResponse:
    value = await service.get_land_cover_type(lat, lon)
    return LandCoverResponse(land_cover_class=value)


@router.get("/land-cover-fractions", response_model=LandCoverFractionsResponse)
async def get_land_cover_fractions(
    service: WorldCoverServiceDependency,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius: Annotated[float, Query(gt=0, le=100_000)],
) -> LandCoverFractionsResponse:
    fractions = await service.get_land_cover_fractions(lat, lon, radius)
    return LandCoverFractionsResponse(fractions)


@router.post(
    "/land-cover-geojson",
    response_model=LandCoverResponse | LandCoverFractionsResponse,
)
async def post_land_cover_geojson(
    service: WorldCoverServiceDependency,
    geojson_file: Annotated[UploadFile, File()],
) -> LandCoverResponse | LandCoverFractionsResponse:
    try:
        geojson = json.loads(await geojson_file.read())
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="GeoJSON file is not valid JSON",
        ) from exc
    if not isinstance(geojson, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="GeoJSON file must contain a JSON object",
        )
    try:
        result = await service.get_land_cover_for_geojson(geojson)
    except GeoJSONNoTileCoverageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if "class" in result:
        return LandCoverResponse(land_cover_class=result["class"])
    return LandCoverFractionsResponse(result)
