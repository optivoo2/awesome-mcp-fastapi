from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    ALLOWED_ORIGINS: List[str]
    ENVIRONMENT: str = "development"
    # Add More here


settings = Settings()
