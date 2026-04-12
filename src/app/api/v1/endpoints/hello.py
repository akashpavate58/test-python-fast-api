from fastapi import APIRouter

from ...models.responses import HelloResponse

router = APIRouter()


@router.get("/hello", response_model=HelloResponse)
def hello() -> HelloResponse:
    return HelloResponse(message="Hello, world!")
