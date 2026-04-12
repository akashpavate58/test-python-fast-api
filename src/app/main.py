from fastapi import FastAPI

from .api.v1.router import router


def create_app() -> FastAPI:
    app = FastAPI(title="FastAPI Service")
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
