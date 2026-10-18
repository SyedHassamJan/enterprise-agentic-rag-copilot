import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router
from app.core.config import BASE_DIR, get_settings
from app.core.logging import configure_logging
from app.services.audit import init_db

configure_logging()
settings = get_settings()
init_db()


app = FastAPI(title=settings.app_name, version=settings.app_version)

if settings.app_env == "production" and settings.admin_api_key in ("", "change-me"):
    logging.getLogger(__name__).warning("ADMIN_API_KEY is unset or default in production: document upload is insecure.")

app.include_router(router)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"app_name": settings.app_name, "version": settings.app_version})
