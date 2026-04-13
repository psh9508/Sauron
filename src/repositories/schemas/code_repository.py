from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB

from src.repositories.schemas.base import Base


class CodeRepository(Base):
    """
    Code repository model.

    repo_info JSONB structure:
    {
        "repository_name": str,  # e.g., "owner/repo" or "group/subgroup/repo"
        "base_url": str | None,  # e.g., "https://git.example.com" for self-hosted
        "auth_config": {
            ...encrypted auth fields based on provider...
            # github: encrypted_pem, app_id, installation_id
            # gitlab: encrypted_access_token
        }
    }
    """

    __tablename__ = "code_repositories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(String(20), nullable=False)
    repo_info = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    @property
    def repository_name(self) -> str:
        return self.repo_info.get("repository_name")

    @property
    def base_url(self) -> str | None:
        return self.repo_info.get("base_url")

    @property
    def auth_config(self) -> dict:
        return self.repo_info.get("auth_config", {})
