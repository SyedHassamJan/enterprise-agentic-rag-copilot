"""Local development entry point. Production (Docker) runs uvicorn directly; see Dockerfile."""
import uvicorn

from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        # Auto-reload only in development; it is slower and can stall on Windows file watchers.
        reload=settings.app_env == "development",
    )
