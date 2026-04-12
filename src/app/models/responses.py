from pydantic import BaseModel


class SuccessResponse(BaseModel):
    message: str
    service_name: str
    environment: str
    request_id: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str


class HelloResponse(SuccessResponse):
    pass
