import asyncio
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidResetCodeError,
    ProhibitedLifecycleError,
    UserNotFoundError,
)
from app.models.models import User
from app.repositories.users import UserRepository
from app.services.mailer import Mailer
from app.services.passwords import PasswordHasher

logger = logging.getLogger(__name__)
email_adapter = TypeAdapter(EmailStr)


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        password_hasher: PasswordHasher,
        mailer: Mailer,
    ):
        self.repository = repository
        self.password_hasher = password_hasher
        self.mailer = mailer

    @staticmethod
    def normalize_email(email: str) -> str:
        return str(email_adapter.validate_python(email)).lower()

    @staticmethod
    def validate_password(password: str) -> None:
        if not 8 <= len(password) <= 128:
            raise ValueError("Password must be between 8 and 128 characters")

    async def authenticate(self, email: str, password: str) -> User:
        try:
            normalized = self.normalize_email(email)
        except ValidationError as exc:
            raise InvalidCredentialsError from exc
        user = await self.repository.get_by_email(normalized)
        if not user or not await asyncio.to_thread(
            self.password_hasher.verify, password, user.password_hash
        ):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InvalidCredentialsError
        user.last_login_at = datetime.now(UTC)
        await self.repository.flush()
        return user

    async def create_user(self, email: str, password: str, *, is_admin: bool) -> User:
        normalized = self.normalize_email(email)
        self.validate_password(password)
        if await self.repository.get_by_email(normalized):
            raise DuplicateEmailError
        password_hash = await asyncio.to_thread(self.password_hasher.hash, password)
        user = User(
            email=normalized,
            password_hash=password_hash,
            bearer_token=None if is_admin else secrets.token_urlsafe(32),
            is_active=True,
            is_admin=is_admin,
        )
        self.repository.add(user)
        await self.repository.flush()
        return user

    async def get_user(self, user_id: int) -> User:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError
        return user

    async def visible_users(self, actor: User) -> list[User]:
        if actor.is_admin:
            return await self.repository.list_all()
        return [actor]

    async def active_admin_count(self) -> int:
        return await self.repository.count_active_admins()

    async def regenerate_token(self, user_id: int) -> User:
        user = await self.get_user(user_id)
        if user.is_admin:
            raise ProhibitedLifecycleError("Administrators cannot have persistent tokens")
        user.bearer_token = secrets.token_urlsafe(32)
        await self.repository.flush()
        return user

    async def toggle_active(self, actor: User, user_id: int) -> User:
        user = await self.get_user(user_id)
        if user.id == actor.id:
            raise ProhibitedLifecycleError("You cannot change your own active status")
        if user.is_admin and user.is_active and await self.repository.count_active_admins() <= 1:
            raise ProhibitedLifecycleError("The last active administrator cannot be deactivated")
        user.is_active = not user.is_active
        await self.repository.flush()
        return user

    async def toggle_admin(self, actor: User, user_id: int) -> User:
        user = await self.get_user(user_id)
        if user.id == actor.id:
            raise ProhibitedLifecycleError("You cannot change your own role")
        if user.is_admin and user.is_active and await self.repository.count_active_admins() <= 1:
            raise ProhibitedLifecycleError("The last active administrator cannot be demoted")
        user.is_admin = not user.is_admin
        user.bearer_token = None if user.is_admin else secrets.token_urlsafe(32)
        await self.repository.flush()
        return user

    async def delete_user(self, actor: User | None, user_id: int) -> None:
        user = await self.get_user(user_id)
        if actor and user.id == actor.id:
            raise ProhibitedLifecycleError("You cannot delete your own account")
        if user.is_admin and user.is_active and await self.repository.count_active_admins() <= 1:
            raise ProhibitedLifecycleError("The last active administrator cannot be deleted")
        await self.repository.delete(user)

    async def delete_user_by_email(self, email: str) -> None:
        normalized = self.normalize_email(email)
        user = await self.repository.get_by_email(normalized)
        if not user:
            raise UserNotFoundError
        await self.delete_user(None, user.id)

    async def request_password_reset(self, email: str) -> None:
        normalized = self.normalize_email(email)
        user = await self.repository.get_by_email(normalized)
        if not user or not user.is_active:
            return
        code = secrets.token_urlsafe(48)
        user.reset_token_hash = hashlib.sha256(code.encode()).hexdigest()
        user.reset_token_expires_at = datetime.now(UTC) + timedelta(minutes=30)
        await self.repository.flush()
        try:
            await self.mailer.send_password_reset(user.email, code)
        except Exception:
            user.reset_token_hash = None
            user.reset_token_expires_at = None
            await self.repository.flush()
            logger.exception("Password-reset delivery failed for user id %s", user.id)

    async def reset_password(self, code: str, password: str) -> User:
        self.validate_password(password)
        digest = hashlib.sha256(code.encode()).hexdigest()
        user = await self.repository.get_by_reset_hash(digest)
        now = datetime.now(UTC)
        expires = user.reset_token_expires_at if user else None
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if not user or not user.is_active or not expires or expires <= now:
            raise InvalidResetCodeError
        user.password_hash = await asyncio.to_thread(self.password_hasher.hash, password)
        user.reset_token_hash = None
        user.reset_token_expires_at = None
        await self.repository.flush()
        return user
