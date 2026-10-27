from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import models
from app.auth_routes import router as auth_router
from app.config import get_settings
from app.dependencies import PermissionDeniedError
from app.rbac_routes import router as rbac_router
from app.hackathon_routes import router as hackathon_router
from app.team_routes import router as team_router
from app.submission_routes import router as submission_router
from app.scoring_routes import router as scoring_router
from app.notification_routes import router as notification_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Lifecycle hooks приложения. Схема БД управляется Alembic-миграциями."""
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Hackathon Platform API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_exception_handler(PermissionDeniedError, _permission_denied_handler)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(rbac_router, prefix="/api/v1")
    app.include_router(hackathon_router, prefix="/api/v1")
    app.include_router(team_router, prefix="/api/v1")
    app.include_router(submission_router, prefix="/api/v1")
    app.include_router(scoring_router, prefix="/api/v1")
    app.include_router(notification_router, prefix="/api/v1")

    from app.health_routes import router as health_router
    app.include_router(health_router, prefix="/api/v1")

    return app


async def _permission_denied_handler(
    _: Request,
    exc: PermissionDeniedError,
) -> JSONResponse:
    """Единый формат ответа 403 при отсутствии RBAC-permission."""
    return JSONResponse(
        status_code=403,
        content={"error": f"Access denied. Required permission: {exc.permission_slug}"},
    )


app = create_app()
