from fastapi import APIRouter

from .endpoints.hello import router as hello_router
from .endpoints.health import router as health_router

router = APIRouter()
router.include_router(hello_router)
router.include_router(health_router, prefix="/health")
