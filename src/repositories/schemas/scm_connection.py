from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB

from src.repositories.schemas.base import Base


class ScmConnection(Base):
    __tablename__ = "scm_connections"
    __table_args__ = (
        UniqueConstraint("provider", "owner", "repo_name", name="uq_scm_connections_repo"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, nullable=False, unique=True)
    provider = Column(String(20), nullable=False)
    owner = Column(String(255), nullable=False)
    repo_name = Column(String(255), nullable=False)
    auth_config = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
