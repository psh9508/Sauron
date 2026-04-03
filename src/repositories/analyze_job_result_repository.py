from __future__ import annotations

from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.schemas.analyze_job_result import AnalyzeJobResult


class AnalyzeJobResultRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def acreate(self, job_id: UUID, result_content: str) -> AnalyzeJobResult:
        stmt = (
            insert(AnalyzeJobResult)
            .values(
                job_id=job_id,
                result_content=result_content,
            )
            .returning(AnalyzeJobResult)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def aget_by_job_id(self, job_id: UUID) -> AnalyzeJobResult | None:
        stmt = select(AnalyzeJobResult).where(AnalyzeJobResult.job_id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
