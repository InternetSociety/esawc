from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.models import User
from app.repositories.tiles import TileRepository
from app.repositories.users import UserRepository
from app.services.mailer import Mailer
from app.services.passwords import password_hasher
from app.services.tokens import TokenService
from app.services.users import UserService
from app.services.worldcover import WorldCoverService

SESSION_COOKIE_NAME = settings.session_cookie_name
bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Security(bearer_scheme),
]


def get_user_repository(session: DatabaseSession) -> UserRepository:
    return UserRepository(session)


def get_tile_repository(session: DatabaseSession) -> TileRepository:
    return TileRepository(session)


def get_user_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repository, password_hasher, Mailer(settings))


def get_worldcover_service(
    repository: Annotated[TileRepository, Depends(get_tile_repository)],
) -> WorldCoverService:
    return WorldCoverService(repository)


async def get_current_user(
    request: Request,
    credentials: BearerCredentials,
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User | None:
    token_service = TokenService(settings)
    if credentials:
        user = await repository.get_by_bearer_token(credentials.credentials)
        if user:
            return user
        email = token_service.decode(credentials.credentials, "access")
        return await repository.get_by_email(email) if email else None

    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        return None
    email = token_service.decode(session_token, "session")
    return await repository.get_by_email(email) if email else None


async def get_current_active_user(
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    if not current_user:
        if request.url.path.startswith("/api") or request.url.path == "/openapi.json":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/"},
        )
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")
    return current_user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return current_user


def require_same_origin(request: Request) -> None:
    """Apply strict Origin/Referer validation to cookie-authenticated mutations."""
    if not request.cookies.get(SESSION_COOKIE_NAME):
        return
    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    parsed = urlparse(source)
    if (parsed.scheme, parsed.netloc) != (request.url.scheme, request.url.netloc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


CurrentUser = Annotated[User, Depends(get_current_active_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin_user)]
UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
WorldCoverServiceDependency = Annotated[WorldCoverService, Depends(get_worldcover_service)]
SameOrigin = Annotated[None, Depends(require_same_origin)]
