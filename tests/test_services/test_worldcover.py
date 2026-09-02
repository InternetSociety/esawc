from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from app.services import worldcover
from app.services.worldcover import WorldCoverService, get_worldcover_tile_id, get_worldcover_url


class FakeTileRepository:
    def __init__(self, tile=None):
        self.tile = tile

    async def get_by_tile_id(self, _tile_id):
        return self.tile

    async def list_all(self):
        return [self.tile] if self.tile else []

    async def list_expired(self, _now):
        return []

    def add(self, tile):
        self.tile = tile

    async def delete(self, _tile):
        self.tile = None

    async def flush(self):
        return None


def write_raster(path, data, *, west: float, north: float, pixel_size: float) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=from_origin(west, north, pixel_size, pixel_size),
    ) as destination:
        destination.write(data, 1)


def test_tile_id_and_url_generation():
    assert get_worldcover_tile_id(-46.5, 37.5) == "S48E036"
    assert get_worldcover_tile_id(-41.3, 174.8) == "S42E174"
    assert get_worldcover_url("S42E174").endswith("ESA_WorldCover_10m_2021_v200_S42E174_Map.tif")


async def test_cached_tile_expiration_uses_configured_days(monkeypatch):
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, _timezone=None):
            return now

    tile = SimpleNamespace(file_path="/app/data/tiles/S42E174.tif")
    repository = FakeTileRepository(tile)
    monkeypatch.setattr(worldcover, "datetime", FixedDateTime)
    monkeypatch.setattr(worldcover.settings, "tile_expiry_days", 30)

    path = await WorldCoverService(repository).get_tile_path(-41.3, 174.8)

    assert path == tile.file_path
    assert tile.last_used_at == now
    assert tile.expires_at == now + timedelta(days=30)


async def test_counts_are_aggregated_across_chunks(tmp_path, monkeypatch):
    raster_path = tmp_path / "tile.tif"
    data = np.array(
        [
            [10, 10, 20, 20],
            [10, 10, 20, 20],
            [30, 30, 40, 40],
            [30, 30, 40, 40],
        ],
        dtype=np.uint8,
    )
    write_raster(raster_path, data, west=0, north=2, pixel_size=0.5)
    service = WorldCoverService(FakeTileRepository())
    service.WINDOW_CHUNK_SIZE = 2

    async def fake_get_tile_path(_lat, _lon):
        return str(raster_path)

    monkeypatch.setattr(service, "get_tile_path", fake_get_tile_path)
    counts = await service._get_land_cover_counts_for_geometries(
        [box(0, 0, 2, 2)], raise_on_empty=True
    )

    assert counts == {10: 4, 20: 4, 30: 4, 40: 4}


async def test_counts_are_aggregated_across_multiple_tiles(tmp_path, monkeypatch):
    south_path = tmp_path / "south.tif"
    north_path = tmp_path / "north.tif"
    write_raster(
        south_path, np.full((6, 6), 10, dtype=np.uint8), west=105, north=48, pixel_size=0.5
    )
    write_raster(
        north_path, np.full((6, 6), 20, dtype=np.uint8), west=105, north=51, pixel_size=0.5
    )
    service = WorldCoverService(FakeTileRepository())

    async def fake_get_tile_path(lat, _lon):
        return str(south_path if lat < 48 else north_path)

    monkeypatch.setattr(service, "get_tile_path", fake_get_tile_path)
    counts = await service._get_land_cover_counts_for_geometries(
        [box(106, 47, 107, 49)], raise_on_empty=True
    )

    assert counts == {10: 4, 20: 4}
