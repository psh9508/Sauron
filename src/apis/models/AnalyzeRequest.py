from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field

from src.apis.models.base_response_model import BaseResponseData


class AnalyzeRequest(BaseModel):
    """Analyze request model.

    - repository_id: Used to lookup provider from database
    - repository_url: Required for GitLab, ignored for GitHub
    """
    repository_id: int = Field(..., description="Source control repository configuration ID")
    repository_url: AnyHttpUrl | None = Field(default=None, description="Repository URL (required for GitLab)")
    error_message: str = Field(..., description="Error message to analyze")
    stack_trace: str = Field(..., description="Stack trace of the error")


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
