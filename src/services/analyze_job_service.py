from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.apis.models.AnalyzeRequest import AnalyzeJobAcceptedRes, AnalyzeJobRes, AnalyzeRequestPayload
from src.repositories.analyze_job_repository import AnalyzeJobRepository
from src.repositories.analyze_job_result_repository import AnalyzeJobResultRepository
from src.repositories.schemas.analyze_job import AnalyzeJob
from src.repositories.schemas.analyze_job_result import AnalyzeJobResult
from src.services.exceptions import AnalyzeJobNotFoundError
from src.services.source_control_service import SourceControlService


class AnalyzeJobService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.analyze_job_repo = AnalyzeJobRepository(session)
        self.analyze_job_result_repo = AnalyzeJobResultRepository(session)

    async def acreate_job(self, request: AnalyzeRequestPayload) -> AnalyzeJobAcceptedRes:
        source_control_service = SourceControlService(self.session)
        # await source_control_service.avalidate_analyze_request(request)

        job_id = uuid4()
        created_job = await self.analyze_job_repo.acreate(
            job_id=job_id,
            repository_id=request.repository_id,
            request=request.model_dump(mode="json"),
        )
        return AnalyzeJobAcceptedRes(
            job_id=created_job.id,
            status="queued",
        )

    async def aget_job(self, job_id: UUID) -> AnalyzeJobRes:
        job = await self.analyze_job_repo.aget_by_id(job_id)
        if job is None:
            raise AnalyzeJobNotFoundError(job_id=job_id)

        result = await self.analyze_job_result_repo.aget_by_job_id(job_id)
        return self._build_job_response(job, result)

    async def aclaim_next_job(self) -> AnalyzeJob | None:
        return await self.analyze_job_repo.aclaim_next_queued()

    async def amark_completed(self, job_id: UUID, result_content: str) -> None:
        updated_job = await self.analyze_job_repo.aget_by_id(job_id)
        if updated_job is None:
            raise AnalyzeJobNotFoundError(job_id=job_id)

        await self.analyze_job_result_repo.acreate(
            job_id=job_id,
            result_content=result_content,
        )
        await self.analyze_job_repo.amark_completed(job_id)

    async def amark_failed(self, job_id: UUID, error_message: str) -> None:
        updated_job = await self.analyze_job_repo.amark_failed(job_id, error_message)
        if updated_job is None:
            raise AnalyzeJobNotFoundError(job_id=job_id)

    def _build_job_response(
        self,
        job: AnalyzeJob,
        result: AnalyzeJobResult | None,
    ) -> AnalyzeJobRes:
        return AnalyzeJobRes(
            job_id=job.id,
            repository_id=job.repository_id,
            status=job.status,
            result_content=result.result_content if result is not None else None,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )
