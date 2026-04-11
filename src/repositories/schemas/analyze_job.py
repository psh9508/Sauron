from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, Uuid, func

from src.repositories.schemas.base import Base


class AnalyzeJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyzeJob(Base):
    __tablename__ = "analyze_jobs"

    id = Column(Uuid, primary_key=True)
    repository_id = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False, default=AnalyzeJobStatus.QUEUED.value)
    error_message_input = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=False)
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    claimed_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
