"""Environment-driven configuration. No secrets are hard-coded."""

import os
from pathlib import Path


class Settings:
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./tms.db")
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    JWT_EXPIRE_HOURS: int = int(os.environ.get("JWT_EXPIRE_HOURS", "8"))
    JWT_ALGORITHM: str = "HS256"
    CORS_ORIGINS: list = [
        o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()
    ]
    AI_PROVIDER: str = os.environ.get("AI_PROVIDER", "mock")
    STORAGE_DIR: Path = Path(os.environ.get("STORAGE_DIR", "./storage"))
    MAX_UPLOAD_BYTES: int = int(
        os.environ.get("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))
    )

    @property
    def is_default_jwt_secret(self) -> bool:
        return self.JWT_SECRET == "dev-secret-change-me"


settings = Settings()
