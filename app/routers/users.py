from collections.abc import Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import EmailStr

from app.dependencies import CurrentAdmin, CurrentUser, SameOrigin, UserServiceDependency
from app.exceptions import DuplicateEmailError, ProhibitedLifecycleError, UserNotFoundError
from app.schemas.schemas import Password
from app.templates import templates

router = APIRouter(tags=["User management"])


async def render_users(
    request: Request,
    user: CurrentUser,
    service: UserServiceDependency,
    *,
    error: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    users = await service.visible_users(user)
    active_admin_count = await service.active_admin_count()
    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "user": user,
            "users": users,
            "active_admin_count": active_admin_count,
            "error": error,
        },
        status_code=status_code,
    )


def error_details(exc: Exception) -> tuple[str, int]:
    if isinstance(exc, DuplicateEmailError):
        return "An account with that email already exists.", status.HTTP_409_CONFLICT
    if isinstance(exc, UserNotFoundError):
        return "The selected account does not exist.", status.HTTP_404_NOT_FOUND
    if isinstance(exc, ProhibitedLifecycleError):
        return str(exc), status.HTTP_400_BAD_REQUEST
    return "The request could not be completed.", status.HTTP_400_BAD_REQUEST


@router.get("/manage-users", include_in_schema=False, response_class=HTMLResponse)
async def manage_users_page(
    request: Request,
    user: CurrentUser,
    service: UserServiceDependency,
) -> Response:
    return await render_users(request, user, service)


@router.post("/users/create", include_in_schema=False, response_class=HTMLResponse)
async def create_user(
    request: Request,
    user: CurrentAdmin,
    _same_origin: SameOrigin,
    service: UserServiceDependency,
    email: Annotated[EmailStr, Form()],
    password: Annotated[Password, Form()],
    is_admin: Annotated[bool, Form()] = False,
) -> Response:
    try:
        await service.create_user(str(email), password, is_admin=is_admin)
    except (DuplicateEmailError, ValueError) as exc:
        message, code = error_details(exc)
        return await render_users(request, user, service, error=message, status_code=code)
    return RedirectResponse("/manage-users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/regen-token", include_in_schema=False, response_class=HTMLResponse)
async def regenerate_token(
    request: Request,
    user_id: int,
    user: CurrentAdmin,
    _same_origin: SameOrigin,
    service: UserServiceDependency,
) -> Response:
    return await run_action(request, user, service, service.regenerate_token(user_id))


@router.post("/users/{user_id}/toggle-active", include_in_schema=False, response_class=HTMLResponse)
async def toggle_active(
    request: Request,
    user_id: int,
    user: CurrentAdmin,
    _same_origin: SameOrigin,
    service: UserServiceDependency,
) -> Response:
    return await run_action(request, user, service, service.toggle_active(user, user_id))


@router.post("/users/{user_id}/toggle-admin", include_in_schema=False, response_class=HTMLResponse)
async def toggle_admin(
    request: Request,
    user_id: int,
    user: CurrentAdmin,
    _same_origin: SameOrigin,
    service: UserServiceDependency,
) -> Response:
    return await run_action(request, user, service, service.toggle_admin(user, user_id))


@router.post("/users/{user_id}/delete", include_in_schema=False, response_class=HTMLResponse)
async def delete_user(
    request: Request,
    user_id: int,
    user: CurrentAdmin,
    _same_origin: SameOrigin,
    service: UserServiceDependency,
) -> Response:
    return await run_action(request, user, service, service.delete_user(user, user_id))


async def run_action(
    request: Request,
    user: CurrentAdmin,
    service: UserServiceDependency,
    action: Coroutine[Any, Any, object],
) -> Response:
    try:
        await action
    except (UserNotFoundError, ProhibitedLifecycleError) as exc:
        message, code = error_details(exc)
        return await render_users(request, user, service, error=message, status_code=code)
    return RedirectResponse("/manage-users", status_code=status.HTTP_303_SEE_OTHER)
