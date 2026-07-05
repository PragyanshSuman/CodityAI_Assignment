from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/codityai"
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    WORKER_HEARTBEAT_INTERVAL: int = 5
    WORKER_POLL_INTERVAL: int = 1
    WORKER_STALE_TIMEOUT: int = 30
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    GEMINI_API_KEY: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
