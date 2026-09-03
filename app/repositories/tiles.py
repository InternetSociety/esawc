from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CachedTile


class TileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tile_id(self, tile_id: str) -> CachedTile | None:
        result = await self.session.execute(select(CachedTile).where(CachedTile.tile_id == tile_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[CachedTile]:
        result = await self.session.execute(select(CachedTile).order_by(CachedTile.tile_id))
        return list(result.scalars())

    async def list_expired(self, now: datetime) -> list[CachedTile]:
        result = await self.session.execute(select(CachedTile).where(CachedTile.expires_at < now))
        return list(result.scalars())

    def add(self, tile: CachedTile) -> None:
        self.session.add(tile)

    async def delete(self, tile: CachedTile) -> None:
        await self.session.delete(tile)

    async def flush(self) -> None:
        await self.session.flush()
