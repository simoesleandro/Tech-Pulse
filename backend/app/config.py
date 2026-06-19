import os
from functools import lru_cache

from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    """Configuração validada na startup (env + defaults)."""

    database_url: str = Field(default="sqlite:///./techpulse.db")
    techpulse_data_dir: str = Field(default=".")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])
    techpulse_api_key: str = Field(default="")
    allow_seed: bool = Field(default=True)
    ingest_batch_size: int = Field(default=5, ge=1, le=100)
    ollama_keep_alive: str = Field(default="5m")
    ingest_on_startup: bool = Field(default=False)
    ingest_interval_seconds: int = Field(default=300, ge=60)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///./techpulse.db"),
            techpulse_data_dir=os.getenv("TECHPULSE_DATA_DIR", "."),
            cors_origins=os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            ),
            techpulse_api_key=os.getenv("TECHPULSE_API_KEY", "").strip(),
            allow_seed=os.getenv("ALLOW_SEED", "true").lower() == "true",
            ingest_batch_size=int(os.getenv("INGEST_BATCH_SIZE", "5")),
            ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "5m"),
            ingest_on_startup=os.getenv("INGEST_ON_STARTUP", "false").lower() == "true",
            ingest_interval_seconds=int(os.getenv("INGEST_INTERVAL_SECONDS", "300")),
        )


@lru_cache
def get_app_config() -> AppConfig:
    return AppConfig.from_env()
