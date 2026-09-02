import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.database import get_db
from app.dependencies import get_user_service
from app.main import app
from app.models.models import Base, User
from app.repositories.users import UserRepository
from app.services.passwords import password_hasher
from app.services.users import UserService

ORIGIN = "http://testserver"


@dataclass
class FakeMailer:
    messages: list[tuple[str, str]] = field(default_factory=list)
    fail: bool = False
    entered: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event | None = None

    async def send_password_reset(self, recipient: str, code: str) -> None:
        self.entered.set()
        await asyncio.sleep(0)
        if self.release:
            await self.release.wait()
        if self.fail:
            raise RuntimeError("delivery failed")
        self.messages.append((recipient, code))


@dataclass
class TestContext:
    client: AsyncClient
    session: AsyncSession
    service: UserService
    mailer: FakeMailer

    async def create_user(
        self,
        email: str,
        password: str = "valid-password",
        *,
        admin: bool = False,
        active: bool = True,
    ) -> User:
        user = await self.service.create_user(email, password, is_admin=admin)
        user.is_active = active
        await self.session.flush()
        return user

    async def login(self, email: str, password: str = "valid-password"):
        return await self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )


@pytest.fixture
async def context(tmp_path: Path):
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        mailer = FakeMailer()
        service = UserService(UserRepository(session), password_hasher, mailer)  # type: ignore[arg-type]

        async def override_get_db():
            async with session.begin_nested():
                yield session

        def override_get_user_service() -> UserService:
            return service

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_user_service] = override_get_user_service
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url=ORIGIN,
        ) as client:
            yield TestContext(client, session, service, mailer)

        app.dependency_overrides.clear()
        await session.close()
        await transaction.rollback()
    await test_engine.dispose()
