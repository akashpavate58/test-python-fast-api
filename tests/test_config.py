import os

from app.core.config import get_settings


def teardown_function(function):
    os.environ.pop("APP_NAME", None)
    os.environ.pop("ENVIRONMENT", None)
    os.environ.pop("API_V1_PREFIX", None)
    os.environ.pop("ALLOWED_CORS_ORIGINS", None)
    get_settings.cache_clear()


def test_default_settings_load_when_env_missing():
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_name == "FastAPI Service"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.log_level == "INFO"
    assert settings.allowed_cors_origins == []
    assert settings.azuresql_connection_string == ""
    assert settings.qdrant_url == ""
    assert settings.qdrant_api_key == ""
    assert settings.external_api_base_url == ""
    assert settings.external_api_timeout_seconds == 10


def test_environment_variable_overrides():
    os.environ["APP_NAME"] = "Test Service"
    os.environ["ENVIRONMENT"] = "production"
    os.environ["API_V1_PREFIX"] = "/api/v1/test"
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_name == "Test Service"
    assert settings.environment == "production"
    assert settings.api_v1_prefix == "/api/v1/test"


def test_allowed_cors_origins_list_parsing():
    os.environ["ALLOWED_CORS_ORIGINS"] = "http://localhost:3000,http://example.com"
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.allowed_cors_origins == [
        "http://localhost:3000",
        "http://example.com",
    ]
