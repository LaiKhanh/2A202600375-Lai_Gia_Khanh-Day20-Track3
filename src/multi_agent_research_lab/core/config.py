"""Application configuration.

Keep config small and explicit. Do not read environment variables directly in agents.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in values:
            values[key] = value
    return values


class Settings(BaseModel):
    """Runtime settings loaded from environment variables or `.env`."""

    app_env: str = Field(default="local")
    log_level: str = Field(default="INFO")

    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = Field(default="gemini-2.5-flash")

    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")

    langsmith_api_key: str | None = Field(default=None)
    langsmith_project: str = Field(default="multi-agent-research-lab")

    tavily_api_key: str | None = Field(default=None)

    max_iterations: int = Field(default=6, ge=1, le=20)
    timeout_seconds: int = Field(default=60, ge=5, le=600)

    def __init__(self, **data: object) -> None:
        merged = self._resolve_values(data)
        super().__init__(**merged)

    @classmethod
    def _resolve_values(cls, data: dict[str, object]) -> dict[str, object]:
        env_file_values = _load_env_file(Path(".env"))
        env_values = dict(os.environ)
        resolved: dict[str, object] = {
            "app_env": env_values.get("APP_ENV", env_file_values.get("APP_ENV", "local")),
            "log_level": env_values.get("LOG_LEVEL", env_file_values.get("LOG_LEVEL", "INFO")),
            "gemini_api_key": env_values.get("GEMINI_API_KEY", env_file_values.get("GEMINI_API_KEY")),
            "gemini_model": env_values.get("GEMINI_MODEL", env_file_values.get("GEMINI_MODEL", "gemini-2.5-flash")),
            "openai_api_key": env_values.get("OPENAI_API_KEY", env_file_values.get("OPENAI_API_KEY")),
            "openai_model": env_values.get("OPENAI_MODEL", env_file_values.get("OPENAI_MODEL", "gpt-4o-mini")),
            "langsmith_api_key": env_values.get("LANGSMITH_API_KEY", env_file_values.get("LANGSMITH_API_KEY")),
            "langsmith_project": env_values.get(
                "LANGSMITH_PROJECT",
                env_file_values.get("LANGSMITH_PROJECT", "multi-agent-research-lab"),
            ),
            "tavily_api_key": env_values.get("TAVILY_API_KEY", env_file_values.get("TAVILY_API_KEY")),
            "max_iterations": env_values.get("MAX_ITERATIONS", env_file_values.get("MAX_ITERATIONS", 6)),
            "timeout_seconds": env_values.get("TIMEOUT_SECONDS", env_file_values.get("TIMEOUT_SECONDS", 60)),
        }
        resolved.update(data)
        return resolved


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
