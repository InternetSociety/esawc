from fastapi.templating import Jinja2Templates

from app.config import settings

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["app_name"] = settings.app_name

__all__ = ["templates"]
