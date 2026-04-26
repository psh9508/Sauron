from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.schemas.analyze_job import AnalyzeJob
from src.repositories.schemas.error_event import ErrorEvent


class ErrorEventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def aupsert(
        self,
        fingerprint: str,
        repository_id: int,
        event_type: str,
    ) -> ErrorEvent:
        stmt = (
            insert(ErrorEvent)
            .values(
                fingerprint=fingerprint,
                repository_id=repository_id,
                event_type=event_type,
                event_count=1,
            )
            .on_conflict_do_update(
                constraint="uq_error_events_fingerprint_repo",
                set_={
                    "event_count": ErrorEvent.event_count + 1,
                    "last_seen": func.now(),
                },
            )
            .returning(ErrorEvent)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def aupdate_analyze_job_id(
        self,
        fingerprint: str,
        repository_id: int,
        analyze_job_id: UUID,
    ) -> None:
        stmt = (
            update(ErrorEvent)
            .where(
                ErrorEvent.fingerprint == fingerprint,
                ErrorEvent.repository_id == repository_id,
            )
            .values(analyze_job_id=analyze_job_id)
        )
        await self.session.execute(stmt)

    async def alist_with_requests(self) -> list[tuple[ErrorEvent, dict | None]]:
        stmt = (
            select(ErrorEvent, AnalyzeJob.request)
            .outerjoin(AnalyzeJob, ErrorEvent.analyze_job_id == AnalyzeJob.id)
            .order_by(ErrorEvent.last_seen.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.all())
