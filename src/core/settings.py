from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    PROJECT_NAME: str = "Awesome MCP FastAPI"
    SECRET_KEY: str
    DATABASE_URL: str

    ALLOWED_ORIGINS: List[str]
    ENVIRONMENT: str = "development"


settings = Settings()
