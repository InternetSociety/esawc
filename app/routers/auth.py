from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr

from app.config import settings
from app.dependencies import CurrentUser, SameOrigin, UserServiceDependency
from app.exceptions import InvalidCredentialsError, InvalidResetCodeError
from app.schemas.schemas import Password, TokenResponse
from app.services.tokens import TokenService
from app.templates import templates

router = APIRouter(tags=["Authentication"])


@router.post("/login", include_in_schema=False, response_class=RedirectResponse)
async def login(
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form()],
    service: UserServiceDependency,
) -> RedirectResponse:
    try:
        user = await service.authenticate(str(email), password)
    except InvalidCredentialsError:
        return RedirectResponse(
            "/?error=invalid_credentials", status_code=status.HTTP_303_SEE_OTHER
        )
    token = TokenService(settings).create(user.email, "session")
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: UserServiceDependency,
) -> TokenResponse:
    try:
        user = await service.authenticate(form_data.username, form_data.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return TokenResponse(access_token=TokenService(settings).create(user.email, "access"))


@router.post("/logout", include_in_schema=False, response_class=RedirectResponse)
async def logout(_user: CurrentUser, _same_origin: SameOrigin) -> RedirectResponse:
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/forgot-password", include_in_schema=False, response_class=HTMLResponse)
async def forgot_password_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "forgot_password.html", {})


@router.post("/forgot-password", include_in_schema=False, response_class=HTMLResponse)
async def forgot_password(
    request: Request,
    email: Annotated[EmailStr, Form()],
    service: UserServiceDependency,
) -> HTMLResponse:
    await service.request_password_reset(str(email))
    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        {"acknowledgement": True},
    )


@router.get("/reset-password", include_in_schema=False, response_class=HTMLResponse)
async def reset_password_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "reset_password.html", {})


@router.post(
    "/reset-password",
    include_in_schema=False,
    response_class=HTMLResponse,
    response_model=None,
)
async def reset_password(
    request: Request,
    code: Annotated[str, Form(min_length=1)],
    password: Annotated[Password, Form()],
    service: UserServiceDependency,
) -> HTMLResponse | RedirectResponse:
    try:
        await service.reset_password(code, password)
    except InvalidResetCodeError:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"error": "The reset code is invalid or expired."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse("/?reset=success", status_code=status.HTTP_303_SEE_OTHER)
