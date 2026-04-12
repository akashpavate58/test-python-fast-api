import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.v1.router import router as api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import init_logging, request_id_ctx_var
from app.models.responses import ErrorResponse


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", request.headers.get("x-request-id") or str(uuid.uuid4()))


def _build_error_payload(error_code: str, message: str, request_id: str) -> dict:
    return ErrorResponse(error_code=error_code, message=message, request_id=request_id).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logging.getLogger("app.main").exception("Application error")
        response = JSONResponse(
            status_code=exc.status_code,
            content=_build_error_payload(
                error_code=exc.error_code,
                message=str(exc) or "Application error.",
                request_id=_get_request_id(request),
            ),
        )
        response.headers["X-Request-ID"] = _get_request_id(request)
        return response

    def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logging.getLogger("app.main").exception("Request validation error")
        response = JSONResponse(
            status_code=422,
            content=_build_error_payload(
                error_code="validation_error",
                message="Invalid request.",
                request_id=_get_request_id(request),
            ),
        )
        response.headers["X-Request-ID"] = _get_request_id(request)
        return response

    def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logging.getLogger("app.main").warning("HTTP exception: %s", exc.detail)
        if exc.status_code == 404:
            error_code = "not_found"
            message = "Resource not found."
        else:
            error_code = "http_error"
            message = str(exc.detail) or "HTTP error."

        response = JSONResponse(
            status_code=exc.status_code,
            content=_build_error_payload(
                error_code=error_code,
                message=message,
                request_id=_get_request_id(request),
            ),
        )
        response.headers["X-Request-ID"] = _get_request_id(request)
        return response

    def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("app.main").exception("Unexpected exception")
        response = JSONResponse(
            status_code=500,
            content=_build_error_payload(
                error_code="internal_error",
                message="Internal server error.",
                request_id=_get_request_id(request),
            ),
        )
        response.headers["X-Request-ID"] = _get_request_id(request)
        return response

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        request_id_ctx_var.set(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    init_logging(settings.log_level)
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

    if settings.allowed_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RequestIDMiddleware)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    register_exception_handlers(app)
    return app


app = create_app()
