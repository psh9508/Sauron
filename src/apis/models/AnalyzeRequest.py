import logging
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from src.apis.models.base_response_model import BaseResponseData

logger = logging.getLogger(__name__)

GIT_COMMIT_SHA_PATTERN = re.compile(r"[0-9a-f]{7,40}")


class StackFrame(BaseModel):
    filename: str
    lineno: int
    function: str
    code: str | None = None


class EventDetail(BaseModel):
    type: str
    value: str
    stacktrace: list[StackFrame] = Field(default=[])


class AnalyzePayload(BaseModel):
    repository_url: AnyHttpUrl | None = Field(default=None, description="Repository URL (required for GitLab)")
    fingerprint: str = Field(..., min_length=32, max_length=32)
    event: EventDetail
    breadcrumbs: list[dict] = Field(default=[], description="Log records leading up to the error")
    git_commit_sha: str | None = Field(
        default=None,
        description="Commit SHA of the running code (GIT_COMMIT_SHA on the SDK side)",
    )

    @field_validator("git_commit_sha", mode="before")
    @classmethod
    def _normalize_git_commit_sha(cls, value: object) -> str | None:
        # A malformed SHA must not drop the error report; analysis falls back to the default branch
        if value is None:
            return None
        sha = str(value).strip().lower()
        if not GIT_COMMIT_SHA_PATTERN.fullmatch(sha):
            logger.warning("Ignoring malformed git_commit_sha: %r", value)
            return None
        return sha

    @property
    def event_type(self) -> str:
        if self.event.stacktrace:
            return "exception"
        return "message"

    @property
    def error_message(self) -> str:
        return f"{self.event.type}: {self.event.value}"

    @property
    def stack_trace(self) -> str:
        if not self.event.stacktrace:
            return ""
        lines = ["Traceback (most recent call last):"]
        for frame in self.event.stacktrace:
            lines.append(f'  File "{frame.filename}", line {frame.lineno}, in {frame.function}')
            if frame.code:
                lines.append(f"    {frame.code}")
        lines.append(f"{self.event.type}: {self.event.value}")
        return "\n".join(lines)


class AnalyzeCreateReq(AnalyzePayload):
    repository_key: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Public key issued when the code repository was registered",
    )


class AnalyzeRequest(AnalyzePayload):
    repository_id: int = Field(..., description="Source control repository configuration ID")


class ErrorEventRes(BaseResponseData):
    id: int = Field(..., description="Error event ID")
    fingerprint: str = Field(..., description="Error fingerprint")
    repository_id: int = Field(..., description="Source control repository configuration ID")
    event_type: str = Field(..., description="Error event type")
    event_count: int = Field(..., description="Total occurrence count")
    first_seen: datetime = Field(..., description="First occurrence time")
    last_seen: datetime = Field(..., description="Last occurrence time")
    analyze_job_id: UUID | None = Field(default=None, description="Associated analyze job ID")
    request: dict | None = Field(default=None, description="Original analyze request data")


class ErrorEventListRes(BaseResponseData):
    errors: list[ErrorEventRes] = Field(default=[], description="List of error events")


class AnalyzeJobRes(BaseResponseData):
    job_id: UUID = Field(..., description="Analyze job ID")
    repository_id: int = Field(..., description="Source control repository configuration ID")
    status: Literal["queued", "running", "completed", "failed"] = Field(
        ...,
        description="Analyze job status",
    )
    result_content: str | None = Field(default=None, description="Analyze result content")
    error_message: str | None = Field(default=None, description="Analyze job error message")
    created_at: datetime = Field(..., description="Analyze job creation time")
    started_at: datetime | None = Field(default=None, description="Analyze job start time")
    finished_at: datetime | None = Field(default=None, description="Analyze job finish time")
