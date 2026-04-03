from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.schemas.analyze_job import AnalyzeJob, AnalyzeJobStatus


class AnalyzeJobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def acreate(
        self,
        job_id: UUID,
        project_id: int,
        error_message_input: str,
        stack_trace: str,
    ) -> AnalyzeJob:
        stmt = (
            insert(AnalyzeJob)
            .values(
                id=job_id,
                project_id=project_id,
                status=AnalyzeJobStatus.QUEUED.value,
                error_message_input=error_message_input,
                stack_trace=stack_trace,
            )
            .returning(AnalyzeJob)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def aget_by_id(self, job_id: UUID) -> AnalyzeJob | None:
        stmt = select(AnalyzeJob).where(AnalyzeJob.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def aclaim_next_queued(self) -> AnalyzeJob | None:
        claim_time = datetime.now()
        claim_subquery = (
            select(AnalyzeJob.id)
            .where(AnalyzeJob.status == AnalyzeJobStatus.QUEUED.value)
            .order_by(AnalyzeJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            update(AnalyzeJob)
            .where(AnalyzeJob.id == claim_subquery)
            .values(
                status=AnalyzeJobStatus.RUNNING.value,
                claimed_at=claim_time,
                started_at=claim_time,
                attempt_count=AnalyzeJob.attempt_count + 1,
                updated_at=claim_time,
            )
            .returning(AnalyzeJob)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def amark_completed(self, job_id: UUID) -> AnalyzeJob | None:
        finish_time = datetime.now()
        stmt = (
            update(AnalyzeJob)
            .where(AnalyzeJob.id == job_id)
            .values(
                status=AnalyzeJobStatus.COMPLETED.value,
                finished_at=finish_time,
                error_message=None,
                updated_at=finish_time,
            )
            .returning(AnalyzeJob)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def amark_failed(self, job_id: UUID, error_message: str) -> AnalyzeJob | None:
        finish_time = datetime.now()
        stmt = (
            update(AnalyzeJob)
            .where(AnalyzeJob.id == job_id)
            .values(
                status=AnalyzeJobStatus.FAILED.value,
                finished_at=finish_time,
                error_message=error_message,
                updated_at=finish_time,
            )
            .returning(AnalyzeJob)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
