from fastapi import APIRouter

from app.models.responses import HealthLiveResponse, HealthReadyResponse
from app.services.health import get_liveness_status, get_readiness_status

router = APIRouter()


@router.get("/live", response_model=HealthLiveResponse)
def live() -> HealthLiveResponse:
    status = get_liveness_status()
    return HealthLiveResponse(**status)


@router.get("/ready", response_model=HealthReadyResponse)
def ready() -> HealthReadyResponse:
    status = get_readiness_status()
    return HealthReadyResponse(**status)
