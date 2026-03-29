from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from src.clients.models.llm_config import LLMConfig


ROOT_DIR = Path(__file__).resolve().parents[2]
ENVIRONMENTS_DIR = ROOT_DIR / "environments"


class AuthServerConfig(BaseModel):
    host: str = Field(..., description="Auth server hostname")
    port: int = Field(..., description="Auth server port")

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class AppSettings(BaseModel):
    env: str = Field(..., description="Active runtime environment")
    config_path: Path = Field(..., description="Resolved config file path")
    auth_server: AuthServerConfig = Field(default_factory=AuthServerConfig)
    llm: LLMConfig = Field(
        default_factory=lambda: LLMConfig(
            provider="gemini",
            model="gemini-2.5-flash",
            temperature=0.3,
        )
    )


def _resolve_environment_name() -> str:
    env_name = os.getenv("env")
    if env_name is None or not env_name.strip():
        raise ValueError("Missing required 'env' value in .env")
    return env_name.strip()


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


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    load_dotenv()

    env_name = _resolve_environment_name()
    config_path = _resolve_config_path(env_name)

    with config_path.open("r", encoding="utf-8") as config_file:
        raw_config = yaml.safe_load(config_file) or {}

    return AppSettings(
        env=env_name,
        config_path=config_path,
        **raw_config,
    )
