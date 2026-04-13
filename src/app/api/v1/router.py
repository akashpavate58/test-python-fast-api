from fastapi import APIRouter

from .endpoints.health import router as health_router
from .endpoints.hello import router as hello_router
from .endpoints.ingestions import router as ingestions_router

router = APIRouter()
router.include_router(hello_router)
router.include_router(health_router, prefix="/health")
router.include_router(ingestions_router)
