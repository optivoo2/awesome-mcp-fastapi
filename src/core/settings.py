from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    ALLOWED_ORIGINS: List[str]
    ENVIRONMENT: str = "development"
    OPENAI_API_KEY: str
    GROQ_API_KEY: str
    GEMINI_API_KEY: str
    QDRANT_URL: str
    QDRANT_API_KEY: str
    POSTGRES_DATABASE_URL: str
    MONGODB_URL: str


settings = Settings()
