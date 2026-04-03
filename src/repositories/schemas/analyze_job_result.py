from sqlalchemy import Column, DateTime, ForeignKey, Text, Uuid, func

from src.repositories.schemas.base import Base


class AnalyzeJobResult(Base):
    __tablename__ = "analyze_job_results"

    job_id = Column(Uuid, ForeignKey("analyze_jobs.id", ondelete="CASCADE"), primary_key=True)
    result_content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
