from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

from src.clients.models.llm_config import LLMConfig


ROOT_DIR = Path(__file__).resolve().parents[2]
ENVIRONMENTS_DIR = ROOT_DIR / "environments"
ENV_VAR_PATTERN = re.compile(r"\$\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|\$(?P<plain>[A-Za-z_][A-Za-z0-9_]*)")


class PostgresConfig(BaseModel):
    host: str = Field(..., description="Postgres hostname")
    port: int = Field(default=5432, description="Postgres port")
    user: str = Field(..., description="Postgres user")
    password: str = Field(..., description="Postgres password")
    database: str = Field(..., description="Postgres database name")


class DatabaseConfig(BaseModel):
    postgres: PostgresConfig


class GitHubSourceControlConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    encryption_key: str = Field(..., alias="ENCRYPTION_KEY", description="SCM PEM encryption key")


class SourceControlConfig(BaseModel):
    github: GitHubSourceControlConfig = Field(default_factory=GitHubSourceControlConfig)


class CorsConfig(BaseModel):
    allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5174"],
        description="Allowed CORS origins",
    )


class AppSettings(BaseModel):
    env: str = Field(..., description="Active runtime environment")
    config_path: Path = Field(..., description="Resolved config file path")
    cors: CorsConfig = Field(default_factory=CorsConfig)
    db: DatabaseConfig | None = Field(default=None)
    source_control: SourceControlConfig | None = Field(default=None)
    llm: LLMConfig = Field(
        default_factory=lambda: LLMConfig(
            provider="gemini",
            model="gemini-2.5-flash",
            temperature=0.3,
        )
    )


def _resolve_environment_name() -> str:
    env_name = os.getenv("ENV")
    if env_name is not None and env_name.strip():
        return env_name.strip()

    raise ValueError(
        "Missing runtime environment name. Set ENV. "
        "A local .env file is optional and only used as a fallback during development."
    )


def _resolve_config_path(env_name: str) -> Path:
    config_path = ENVIRONMENTS_DIR / env_name / "config.yaml"
    if not config_path.is_file():
        available_envs = sorted(
            path.name for path in ENVIRONMENTS_DIR.iterdir() if path.is_dir()
        )
        raise FileNotFoundError(
            f"Config file not found for env='{env_name}': {config_path}. "
            f"Available environments: {', '.join(available_envs)}"
        )
    return config_path


def _load_config_yaml(config_path: Path) -> dict:
    yaml_content = config_path.read_text(encoding="utf-8")
    expanded_content = os.path.expandvars(yaml_content)

    unresolved_vars = sorted(
        {
            match.group("braced") or match.group("plain")
            for match in ENV_VAR_PATTERN.finditer(expanded_content)
        }
    )
    if unresolved_vars:
        unresolved_var_list = ", ".join(unresolved_vars)
        raise ValueError(
            f"Unresolved environment variables in {config_path}: {unresolved_var_list}"
        )

    return yaml.safe_load(expanded_content) or {}


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    try:
        env_name = _resolve_environment_name()
    except ValueError:
        # Load local development defaults only when the runtime did not inject them.
        load_dotenv(override=False)
        env_name = _resolve_environment_name()

    config_path = _resolve_config_path(env_name)
    raw_config = _load_config_yaml(config_path)

    return AppSettings(
        env=env_name,
        config_path=config_path,
        **raw_config,
    )
