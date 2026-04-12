from typing import TypedDict


class DependencyStatus(TypedDict):
    azuresql: str
    qdrant: str
    external_api: str


def get_liveness_status() -> dict[str, str]:
    return {"status": "healthy"}


def get_readiness_status() -> dict[str, object]:
    return {
        "status": "ready",
        "dependencies": {
            "azuresql": "not_configured",
            "qdrant": "not_configured",
            "external_api": "not_configured",
        },
    }
