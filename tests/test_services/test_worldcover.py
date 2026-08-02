from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.config import tile_expiry
from app.services import worldcover
from app.services.worldcover import get_worldcover_tile_id, get_worldcover_url


class _CachedResult:
    def __init__(self, tile):
        self.tile = tile

    def scalar_one_or_none(self):
        return self.tile


class _CachedTileDB:
    def __init__(self, tile):
        self.tile = tile

    async def execute(self, _query):
        return _CachedResult(self.tile)

    async def commit(self):
        pass


def test_tile_id_calculation():
    # Example provided by user: S48E036 covers 36°E–39°E and 48°S–45°S
    # My logic: 
    # lat = -46.5, lon = 37.5
    # tile_lat = floor(-46.5 / 3) * 3 = -16 * 3 = -48
    # tile_lon = floor(37.5 / 3) * 3 = 12 * 3 = 36
    # -> S48E036
    assert get_worldcover_tile_id(-46.5, 37.5) == "S48E036"
    
    # Another example: -41.3, 174.8
    # tile_lat = floor(-41.3 / 3) * 3 = -14 * 3 = -42
    # tile_lon = floor(174.8 / 3) * 3 = 58 * 3 = 174
    # -> S42E174
    assert get_worldcover_tile_id(-41.3, 174.8) == "S42E174"


def test_url_generation():
    tile_id = "S42E174"
    url = get_worldcover_url(tile_id)
    assert url == "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_S42E174_Map.tif"


def test_tile_expiry_defaults_to_one_year():
    assert tile_expiry == 365


@pytest.mark.asyncio
async def test_cached_tile_expiration_uses_configured_days(monkeypatch):
    now = datetime.fromisoformat("2026-08-02T12:00:00")
    configured_expiry = 30

    class FixedDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return now

    cached_tile = SimpleNamespace(
        file_path="/app/data/tiles/S42E174.tif",
        last_used_at=None,
        expires_at=None,
    )
    db = _CachedTileDB(cached_tile)
    monkeypatch.setattr(worldcover, "datetime", FixedDateTime)
    monkeypatch.setattr(worldcover, "tile_expiry", configured_expiry)

    path = await worldcover.WorldCoverService(db).get_tile_path(-41.3, 174.8)

    assert path == cached_tile.file_path
    assert cached_tile.last_used_at == now
    assert cached_tile.expires_at == now + timedelta(days=configured_expiry)
