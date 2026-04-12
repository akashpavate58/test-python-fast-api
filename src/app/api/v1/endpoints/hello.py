from fastapi import APIRouter, Request

from app.models.responses import SuccessResponse

router = APIRouter()


def _build_success_response(request: Request, message: str) -> SuccessResponse:
    settings = request.app.state.settings
    return SuccessResponse(
        message=message,
        service_name=settings.app_name,
        environment=settings.environment,
        request_id=request.state.request_id,
    )


@router.get("/hello", response_model=SuccessResponse)
def hello(request: Request) -> SuccessResponse:
    return _build_success_response(request, "Hello, world!")


@router.get("/test-validation", response_model=SuccessResponse)
def test_validation(request: Request, count: int) -> SuccessResponse:
    return _build_success_response(request, f"Validated count={count}")


@router.get("/test-error", response_model=SuccessResponse)
def test_error() -> SuccessResponse:
    raise RuntimeError("Simulated internal failure.")
