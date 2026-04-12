from fastapi import APIRouter, Depends, Request

from app.core.config import AppSettings, get_settings
from app.models.responses import HelloResponse

router = APIRouter()


class HelloService:
    def __init__(self, settings: AppSettings) -> None:
        self.service_name = settings.app_name
        self.environment = settings.environment

    def get_message(self) -> str:
        return "Hello, World!"


def get_hello_service(settings: AppSettings = Depends(get_settings)) -> HelloService:
    return HelloService(settings)


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _build_success_response(service: HelloService, request_id: str) -> HelloResponse:
    return HelloResponse(
        message=service.get_message(),
        service_name=service.service_name,
        environment=service.environment,
        request_id=request_id,
    )


@router.get("/hello", response_model=HelloResponse)
def hello(
    request: Request,
    hello_service: HelloService = Depends(get_hello_service),
) -> HelloResponse:
    return _build_success_response(hello_service, _get_request_id(request))


@router.get("/test-validation", response_model=HelloResponse)
def test_validation(
    request: Request,
    count: int,
    hello_service: HelloService = Depends(get_hello_service),
) -> HelloResponse:
    return _build_success_response(hello_service, _get_request_id(request))


@router.get("/test-error", response_model=HelloResponse)
def test_error() -> HelloResponse:
    raise RuntimeError("Simulated internal failure.")
