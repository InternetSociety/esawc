import asyncio

import markdown
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.config import settings
from app.dependencies import (
    CurrentAdmin,
    CurrentUser,
    WorldCoverServiceDependency,
    get_current_user,
)
from app.models.models import User
from app.templates import templates

router = APIRouter(tags=["UI"])


@router.get("/", include_in_schema=False, response_class=HTMLResponse)
async def home(
    request: Request,
    user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    if user and not user.is_active:
        user = None
    return templates.TemplateResponse(request, "index.html", {"user": user})


@router.get("/app-docs", include_in_schema=False, response_class=HTMLResponse)
async def app_docs(request: Request, user: CurrentUser) -> HTMLResponse:
    content = await asyncio.to_thread(settings.guide_path.read_text, encoding="utf-8")
    rendered = await asyncio.to_thread(
        markdown.markdown,
        content,
        extensions=["fenced_code", "tables"],
    )
    return templates.TemplateResponse(
        request,
        "app_docs.html",
        {"content": rendered, "user": user},
    )


@router.get("/tile-cache", include_in_schema=False, response_class=HTMLResponse)
async def tile_cache_page(
    request: Request,
    user: CurrentAdmin,
    service: WorldCoverServiceDependency,
) -> HTMLResponse:
    tiles = await service.list_cached_tiles()
    return templates.TemplateResponse(
        request,
        "tile_cache.html",
        {"tiles": tiles, "user": user},
    )
