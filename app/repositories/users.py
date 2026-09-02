from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_bearer_token(self, token: str) -> User | None:
        result = await self.session.execute(select(User).where(User.bearer_token == token))
        return result.scalar_one_or_none()

    async def get_by_reset_hash(self, digest: str) -> User | None:
        result = await self.session.execute(select(User).where(User.reset_token_hash == digest))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.email))
        return list(result.scalars())

    async def count_active_admins(self) -> int:
        result = await self.session.execute(
            select(func.count(User.id)).where(User.is_admin.is_(True), User.is_active.is_(True))
        )
        return int(result.scalar_one())

    def add(self, user: User) -> None:
        self.session.add(user)

    async def delete(self, user: User) -> None:
        await self.session.delete(user)

    async def flush(self) -> None:
        await self.session.flush()
