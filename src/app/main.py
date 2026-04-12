import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import init_logging


def register_exception_handlers(app: FastAPI) -> None:
    def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        logging.getLogger("app.main").exception("Application error")
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc) or "Application error."},
        )

    def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("app.main").exception("Unexpected exception")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_logging()
    settings = get_settings()
    logger = logging.getLogger("app.main")
    logger.info(
        "Starting application",
        extra={"app_name": settings.app_name, "environment": settings.environment},
    )

    app.state.settings = settings
    app.state.azuresql_client = None
    app.state.qdrant_client = None
    app.state.external_api_client = None

    yield

    logger.info("Shutting down application")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    register_exception_handlers(app)
    return app


app = create_app()
