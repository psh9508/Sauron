import asyncio
import logging

from src.apis.models.AnalyzeRequest import AnalyzeRequest
from src.core.database import init_db_session, session_scope
from src.services.analyze_job_service import AnalyzeJobService
from src.services.analyze_service import run_analyze


logger = logging.getLogger(__name__)

MAX_CONCURRENT_JOBS = 20


class AnalyzeJobWorker:
    def __init__(self, interval_seconds: float = 0.5, max_concurrent_jobs: int = MAX_CONCURRENT_JOBS):
        self.interval_seconds = interval_seconds
        self.semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self.tasks: set[asyncio.Task] = set()
        self.running = False

    async def arun(self) -> None:
        init_db_session()
        self.running = True
        logger.info("Analyze job worker started")

        while self.running:
            await self.semaphore.acquire()
            claimed_job = await self._aclaim_next_job()
            if claimed_job is None:
                self.semaphore.release()
                await asyncio.sleep(self.interval_seconds)
                continue

            task = asyncio.create_task(self._aprocess(claimed_job))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            task.add_done_callback(lambda _: self.semaphore.release())

        logger.info("Analyze job worker stopped")

    async def _aprocess(self, claimed_job) -> None:
        request = AnalyzeRequest.model_validate(claimed_job.request)
        try:
            result_content = await run_analyze(request)
        except Exception as exc:
            logger.exception("Analyze job failed: %s", claimed_job.id)
            await self._amark_failed(claimed_job.id, str(exc))
            return

        await self._amark_completed(claimed_job.id, result_content)

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
