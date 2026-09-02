import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import settings
from app.database import engine
from app.dependencies import CurrentUser
from app.exceptions import (
    DomainError,
    DuplicateEmailError,
    InvalidResetCodeError,
    ProhibitedLifecycleError,
    TileDownloadError,
    UserNotFoundError,
)
from app.routers import api, auth, ui, users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.include_router(auth.router)
    application.include_router(ui.router)
    application.include_router(users.router)
    application.include_router(api.router)
    register_exception_handlers(application)
    register_documentation_routes(application)
    return application


def register_exception_handlers(application: FastAPI) -> None:
    status_by_error: dict[type[DomainError], int] = {
        DuplicateEmailError: status.HTTP_409_CONFLICT,
        UserNotFoundError: status.HTTP_404_NOT_FOUND,
        ProhibitedLifecycleError: status.HTTP_400_BAD_REQUEST,
        InvalidResetCodeError: status.HTTP_400_BAD_REQUEST,
        TileDownloadError: status.HTTP_502_BAD_GATEWAY,
    }

    @application.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        detail = "The request could not be completed"
        if isinstance(exc, TileDownloadError):
            detail = "Land-cover data is temporarily unavailable"
        return JSONResponse(
            status_code=status_by_error.get(type(exc), status.HTTP_400_BAD_REQUEST),
            content={"detail": detail},
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unexpected error during %s %s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )


def register_documentation_routes(application: FastAPI) -> None:
    @application.get("/openapi.json", include_in_schema=False)
    async def protected_openapi(
        _user: CurrentUser,
    ) -> dict:
        return get_openapi(
            title=application.title,
            version=application.version,
            routes=application.routes,
        )

    @application.get("/docs", include_in_schema=False, response_class=HTMLResponse)
    async def protected_docs(user: CurrentUser) -> HTMLResponse:
        administration = (
            '<a class="nav-link" href="/tile-cache">Tile cache</a>' if user.is_admin else ""
        )
        token = None if user.is_admin else user.bearer_token
        token_script = ""
        if token:
            token_script = (
                "window.addEventListener('load', () => {"
                "const timer = setInterval(() => {"
                "if (window.ui) { clearInterval(timer); "
                f"window.ui.preauthorizeApiKey('BearerAuth', {json.dumps(token)}); }}"
                "}, 100); });"
            )
        return HTMLResponse(
            f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{settings.app_name} - API</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <nav class="navbar navbar-expand-lg bg-dark navbar-dark">
    <div class="container">
      <a class="navbar-brand" href="/">{settings.app_name}</a>
      <div class="navbar-nav ms-auto flex-row gap-3">
        <a class="nav-link" href="/docs">API</a>
        <a class="nav-link" href="/app-docs">Guide</a>
        <a class="nav-link" href="/manage-users">Users</a>
        {administration}
        <form action="/logout" method="post">
          <button class="btn btn-link nav-link" type="submit">Sign out</button>
        </form>
      </div>
    </div>
  </nav>
  <main class="container py-5"><div id="swagger-ui"></div></main>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({{
      url: '/openapi.json', dom_id: '#swagger-ui', persistAuthorization: true
    }});
    {token_script}
  </script>
</body>
</html>"""
        )


app = create_app()
