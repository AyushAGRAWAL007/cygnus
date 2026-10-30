"""Configuration: the ONE place that reads environment variables.

Why it exists: secrets (API keys) must never be hard-coded or sent to the
browser. Everything the backend needs comes from `.env` (local) or real
environment variables (deployment) and is exposed through `settings`.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Cygnus"
    app_env: str = "development"
    # Where SQLite stores the order/return progress. A plain file on disk.
    database_path: str = str(REPO_ROOT / "backend" / "cygnus.db")
    # Browser origins allowed to call this API directly (Vite dev server).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    auth_session_ttl_seconds: int = Field(default=28800, ge=60, le=604800)
    auth_trusted_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str | None = None
    integration_encryption_key: SecretStr | None = None

    @field_validator("auth_trusted_origins", "cors_origins")
    @classmethod
    def explicit_origins(cls, value: str) -> str:
        from urllib.parse import urlsplit
        origins = [part.strip() for part in value.split(",") if part.strip()]
        if not origins:
            raise ValueError("At least one explicit origin is required")
        for origin in origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username or parsed.password or parsed.path
                    or parsed.query or parsed.fragment or "*" in origin):
                raise ValueError("Origins must be explicit HTTP(S) origins without paths")
        return value

    @property
    def auth_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.auth_trusted_origins.split(",") if origin.strip()]

    # --- Nebius Token Factory (OpenAI-compatible API) ---
    nebius_api_key: SecretStr | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    # Must be copied EXACTLY from GET /v1/models (casing differs between models).
    nebius_model_id: str = "nvidia/nemotron-3-super-120b-a12b"

    # --- NVIDIA API Catalog (OpenAI-compatible API) ---
    nvidia_api_key: SecretStr | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_configured(self) -> bool:
        return bool(self.nebius_api_key and self.nebius_api_key.get_secret_value())

    @property
    def nvidia_configured(self) -> bool:
        return bool(self.nvidia_api_key and self.nvidia_api_key.get_secret_value().strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
