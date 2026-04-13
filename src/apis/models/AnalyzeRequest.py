from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field, TypeAdapter

from src.apis.models.base_response_model import BaseResponseData


class BaseAnalyzeRequest(BaseModel):
    provider: Literal["github", "gitlab"] = Field(..., description="Source control provider")
    repository_id: int = Field(..., description="Source control repository configuration ID")
    error_message: str = Field(..., description="Error message to analyze")
    stack_trace: str = Field(..., description="Stack trace of the error")


class GitHubAnalyzeRequest(BaseAnalyzeRequest):
    provider: Literal["github"] = Field(default="github", description="Source control provider")


class GitLabAnalyzeRequest(BaseAnalyzeRequest):
    provider: Literal["gitlab"] = Field(default="gitlab", description="Source control provider")
    repository_url: AnyHttpUrl = Field(..., description="GitLab repository URL to analyze")


AnalyzeRequestPayload = GitHubAnalyzeRequest | GitLabAnalyzeRequest
AnalyzeRequest = Annotated[AnalyzeRequestPayload, Field(discriminator="provider")]
_ANALYZE_REQUEST_ADAPTER = TypeAdapter(AnalyzeRequest)


def parse_analyze_request(payload: object) -> AnalyzeRequestPayload:
    return _ANALYZE_REQUEST_ADAPTER.validate_python(payload)


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
