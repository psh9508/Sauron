import asyncio
import logging

from src.apis.models.AnalyzeRequest import AnalyzeRequest
from src.core.database import init_db_session, session_scope
from src.services.analyze_job_service import AnalyzeJobService
from src.services.analyze_service import run_analyze


logger = logging.getLogger(__name__)


class AnalyzeJobWorker:
    def __init__(self, interval_seconds: float = 0.5, initialize_db: bool = True):
        self.interval_seconds = interval_seconds
        self.initialize_db = initialize_db
        self.running = False

    async def arun(self) -> None:
        if self.initialize_db:
            init_db_session()
        self.running = True
        logger.info("Analyze job worker started")

        while self.running:
            claimed_job = await self._aclaim_next_job()
            if claimed_job is None:
                await asyncio.sleep(self.interval_seconds)
                continue

            request = AnalyzeRequest(**claimed_job.request)

            try:
                result_content = await run_analyze(request)
            except Exception as exc:
                logger.exception("Analyze job failed: %s", claimed_job.id)
                await self._amark_failed(claimed_job.id, str(exc))
                continue

            await self._amark_completed(claimed_job.id, result_content)

        logger.info("Analyze job worker stopped")

    async def astop(self) -> None:
        self.running = False

    async def _aclaim_next_job(self):
        async with session_scope() as session:
            service = AnalyzeJobService(session)
            return await service.aclaim_next_job()

    async def _amark_completed(self, job_id, result_content: str) -> None:
        async with session_scope() as session:
            service = AnalyzeJobService(session)
            await service.amark_completed(job_id, result_content)

    async def _amark_failed(self, job_id, error_message: str) -> None:
        async with session_scope() as session:
            service = AnalyzeJobService(session)
            await service.amark_failed(job_id, error_message)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    worker = AnalyzeJobWorker()
    await worker.arun()


if __name__ == "__main__":
    asyncio.run(main())
