from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.services.analyze_job_service import AnalyzeJobService


def get_analyze_job_service(
    session: AsyncSession = Depends(get_session),
) -> AnalyzeJobService:
    return AnalyzeJobService(session)
