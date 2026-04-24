from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field

from src.apis.models.base_response_model import BaseResponseData


class StackFrame(BaseModel):
    filename: str
    lineno: int
    function: str
    code: str


class ExceptionDetail(BaseModel):
    type: str
    value: str
    category: str | None = None
    stacktrace: list[StackFrame] = Field(default=[])


class AnalyzeRequest(BaseModel):
    repository_id: int = Field(..., description="Source control repository configuration ID")
    repository_url: AnyHttpUrl | None = Field(default=None, description="Repository URL (required for GitLab)")
    exception: ExceptionDetail
    breadcrumbs: list[dict] = Field(default=[], description="Log records leading up to the error")

    @property
    def error_message(self) -> str:
        return f"{self.exception.type}: {self.exception.value}"

    @property
    def stack_trace(self) -> str:
        lines = ["Traceback (most recent call last):"]
        for frame in self.exception.stacktrace:
            lines.append(f'  File "{frame.filename}", line {frame.lineno}, in {frame.function}')
            lines.append(f"    {frame.code}")
        lines.append(self.error_message)
        return "\n".join(lines)


class AnalyzeJobAcceptedRes(BaseResponseData):
    job_id: UUID = Field(..., description="Analyze job ID")
    status: Literal["queued"] = Field(default="queued", description="Analyze job status")


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
