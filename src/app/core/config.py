from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    app_name: str = "FastAPI Service"
    app_env: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
