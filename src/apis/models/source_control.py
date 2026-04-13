from datetime import datetime
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from src.apis.models.base_response_model import BaseResponseData


# Auth config types for different providers
class GitHubAppAuthConfig(BaseModel):
    app_id: str = Field(..., description="GitHub App ID")
    installation_id: str = Field(..., description="GitHub Installation ID")
    pem: str = Field(..., description="GitHub App private key PEM contents")


class GitLabPatAuthConfig(BaseModel):
    access_token: str = Field(..., description="GitLab Personal Access Token")


class RepoInfo(BaseModel):
    repository_name: str = Field(..., description="Repository name (e.g., 'owner/repo' or 'group/subgroup/repo')")
    base_url: str | None = Field(default=None, description="Base URL for self-hosted instances (e.g., https://git.example.com)")
    auth_config: GitHubAppAuthConfig | GitLabPatAuthConfig = Field(
        ..., description="Authentication configuration"
    )


class CodeRepositoryCreateReq(BaseModel):
    provider: Literal["github", "gitlab"] = Field(..., description="Source control provider")
    repo_info: RepoInfo = Field(..., description="Repository information")


class RepoInfoRes(BaseModel):
    repository_name: str = Field(..., description="Repository name")
    base_url: str | None = Field(default=None, description="Base URL for self-hosted instances")


class CodeRepositoryRes(BaseResponseData):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Code repository ID")
    provider: Literal["github", "gitlab"] = Field(..., description="Source control provider")
    repo_info: RepoInfoRes = Field(..., description="Repository information")
    is_active: bool = Field(..., description="Whether the repository is active")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Update time")


class CodeRepositoryListRes(BaseResponseData):
    repositories: list[CodeRepositoryRes] = Field(
        default_factory=list,
        description="Code repository list",
    )


class SourceControlAccessTokenRes(BaseResponseData):
    provider: Literal["github", "gitlab"] = Field(..., description="Source control provider")
    access_token: str = Field(..., description="Access token for the source control provider")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_at: datetime | None = Field(default=None, description="Token expiration time")
    repo_url: AnyHttpUrl = Field(..., description="Repository URL of the project")


# Legacy aliases for backwards compatibility
ScmConnectionCreateReq = CodeRepositoryCreateReq
ScmConnectionRes = CodeRepositoryRes
ScmConnectionListRes = CodeRepositoryListRes
