from sqlalchemy import BigInteger, Column, DateTime, Integer, String, UniqueConstraint, Uuid, func

from src.repositories.schemas.base import Base


class ErrorEvent(Base):
    __tablename__ = "error_events"
    __table_args__ = (
        UniqueConstraint("fingerprint", "repository_id", name="uq_error_events_fingerprint_repo"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    fingerprint = Column(String(32), nullable=False, index=True)
    repository_id = Column(BigInteger, nullable=False)
    event_type = Column(String(20), nullable=False)
    event_count = Column(Integer, nullable=False, default=1, server_default="1")
    analyze_job_id = Column(Uuid, nullable=True)
    first_seen = Column(DateTime, nullable=False, server_default=func.now())
    last_seen = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
