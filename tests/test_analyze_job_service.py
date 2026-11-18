"""AnalyzeJobService.acreate_job: when a recurring fingerprint gets a new analysis job."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.apis.models.AnalyzeRequest import AnalyzeCreateReq, EventDetail
from src.repositories.analyze_job_repository import MAX_ANALYZE_ATTEMPTS
from src.repositories.schemas.analyze_job import AnalyzeJobStatus
from src.services.analyze_job_service import AnalyzeJobService

FINGERPRINT = "a" * 32
REPOSITORY_ID = 1


class FakeErrorEventRepo:
    def __init__(self):
        self.event = None

    async def aupsert(self, fingerprint, repository_id, event_type):
        if self.event is None:
            self.event = SimpleNamespace(event_count=1, analyze_job_id=None)
        else:
            self.event.event_count += 1
        return self.event

    async def aupdate_analyze_job_id(self, fingerprint, repository_id, analyze_job_id):
        self.event.analyze_job_id = analyze_job_id


class FakeAnalyzeJobRepo:
    def __init__(self):
        self.jobs = {}

    async def acreate(self, job_id, repository_id, request):
        job = SimpleNamespace(
            id=job_id, status=AnalyzeJobStatus.QUEUED.value, request=request, attempt_count=0, error_message=None
        )
        self.jobs[job_id] = job
        return job

    async def aget_by_id(self, job_id):
        return self.jobs.get(job_id)

    async def arequeue_failed(self, job_id):
        job = self.jobs.get(job_id)
        if job is None or job.status != AnalyzeJobStatus.FAILED.value or job.attempt_count >= MAX_ANALYZE_ATTEMPTS:
            return None
        job.status = AnalyzeJobStatus.QUEUED.value
        job.error_message = None
        return job


class FakeCodeRepoRepo:
    async def aget_active_by_public_key(self, public_key):
        return SimpleNamespace(id=REPOSITORY_ID)


@pytest.fixture
def service():
    service = AnalyzeJobService(session=None)
    service.error_event_repo = FakeErrorEventRepo()
    service.analyze_job_repo = FakeAnalyzeJobRepo()
    service.code_repo_repository = FakeCodeRepoRepo()
    return service


def _create(service):
    req = AnalyzeCreateReq(
        repository_key="key",
        fingerprint=FINGERPRINT,
        event=EventDetail(type="ValueError", value="boom"),
    )
    asyncio.run(service.acreate_job(req))
    return service.error_event_repo.event.analyze_job_id


def _fail(service, job_id):
    job = service.analyze_job_repo.jobs[job_id]
    job.status = AnalyzeJobStatus.FAILED.value
    job.attempt_count += 1
    job.error_message = "503 UNAVAILABLE"


def test_first_occurrence_creates_job(service):
    job_id = _create(service)
    assert job_id is not None
    assert len(service.analyze_job_repo.jobs) == 1


@pytest.mark.parametrize(
    "status",
    [AnalyzeJobStatus.QUEUED, AnalyzeJobStatus.RUNNING, AnalyzeJobStatus.COMPLETED],
)
def test_recurrence_leaves_job_that_has_not_failed(service, status):
    first = _create(service)
    service.analyze_job_repo.jobs[first].status = status.value

    assert _create(service) == first
    assert len(service.analyze_job_repo.jobs) == 1
    assert service.analyze_job_repo.jobs[first].status == status.value


def test_recurrence_after_failure_requeues_same_job(service):
    first = _create(service)
    _fail(service, first)

    assert _create(service) == first

    job = service.analyze_job_repo.jobs[first]
    assert len(service.analyze_job_repo.jobs) == 1
    assert job.status == AnalyzeJobStatus.QUEUED.value
    assert job.error_message is None
    assert job.attempt_count == 1
    assert service.error_event_repo.event.event_count == 2


def test_job_that_used_all_attempts_stays_failed(service):
    first = _create(service)
    for _ in range(MAX_ANALYZE_ATTEMPTS - 1):
        _fail(service, first)
        _create(service)
        assert service.analyze_job_repo.jobs[first].status == AnalyzeJobStatus.QUEUED.value

    _fail(service, first)
    _create(service)

    job = service.analyze_job_repo.jobs[first]
    assert job.attempt_count == MAX_ANALYZE_ATTEMPTS
    assert job.status == AnalyzeJobStatus.FAILED.value
    assert job.error_message == "503 UNAVAILABLE"


def test_recurrence_with_missing_job_creates_new_job(service):
    _create(service)
    service.error_event_repo.event.analyze_job_id = uuid4()

    second = _create(service)

    assert second in service.analyze_job_repo.jobs
