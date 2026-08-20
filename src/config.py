"""Centralized, type-safe app configuration.

Everything the app needs from the environment flows through here so that
no other module reads os.environ directly — one place to see what's
configurable, one place to validate it at startup.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loads from .env (see .env.example) with sane local-dev defaults."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM gateway ---
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # --- App ---
    environment: str = "development"
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = "sqlite:///./data/database.db"

    # --- CORS ---
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — avoids re-parsing .env on every import."""
    return Settings()
