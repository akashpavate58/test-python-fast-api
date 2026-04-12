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


class HealthLiveResponse(BaseModel):
    status: str


class HealthDependencyStatus(BaseModel):
    azuresql: str
    qdrant: str
    external_api: str


class HealthReadyResponse(BaseModel):
    status: str
    dependencies: HealthDependencyStatus
