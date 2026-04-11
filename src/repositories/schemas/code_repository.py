from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB

from src.repositories.schemas.base import Base


class CodeRepository(Base):
    """
    Code repository model.

    repo_info JSONB structure:
    {
        "owner": str,
        "repo_name": str,
        "auth_config": {
            "type": "github_app" | "gitlab_pat",
            ...encrypted auth fields...
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
    def owner(self) -> str:
        return self.repo_info.get("owner")

    @property
    def repo_name(self) -> str:
        return self.repo_info.get("repo_name")

    @property
    def auth_config(self) -> dict:
        return self.repo_info.get("auth_config", {})
