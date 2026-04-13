from datetime import datetime
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from src.apis.models.base_response_model import BaseResponseData


class GitHubAppAuthConfig(BaseModel):
    app_id: str = Field(..., description="GitHub App ID")
    installation_id: str = Field(..., description="GitHub Installation ID")
    pem: str = Field(..., description="GitHub App private key PEM contents")


class GitLabPatAuthConfig(BaseModel):
    access_token: str = Field(..., description="GitLab Personal Access Token")


class GitHubRepoInfoCreate(BaseModel):
    repository_name: str = Field(..., description="Repository name (e.g., 'owner/repo')")
    auth_config: GitHubAppAuthConfig = Field(..., description="GitHub App authentication configuration")


class GitLabRepoInfoCreate(BaseModel):
    base_url: AnyHttpUrl = Field(..., description="Base URL for the GitLab instance")
    auth_config: GitLabPatAuthConfig = Field(..., description="GitLab PAT authentication configuration")


class GitHubCodeRepositoryCreateReq(BaseModel):
    provider: Literal["github"] = Field(default="github", description="Source control provider")
    repo_info: GitHubRepoInfoCreate = Field(..., description="GitHub repository information")


class GitLabCodeRepositoryCreateReq(BaseModel):
    provider: Literal["gitlab"] = Field(default="gitlab", description="Source control provider")
    repo_info: GitLabRepoInfoCreate = Field(..., description="GitLab repository information")


CodeRepositoryCreateReqPayload = GitHubCodeRepositoryCreateReq | GitLabCodeRepositoryCreateReq
CodeRepositoryCreateReq = Annotated[CodeRepositoryCreateReqPayload, Field(discriminator="provider")]


class GitHubRepoInfoRes(BaseModel):
    repository_name: str = Field(..., description="Repository name")


class GitLabRepoInfoRes(BaseModel):
    base_url: AnyHttpUrl = Field(..., description="Base URL for the GitLab instance")


class GitHubCodeRepositoryRes(BaseResponseData):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Code repository ID")
    provider: Literal["github"] = Field(default="github", description="Source control provider")
    repo_info: GitHubRepoInfoRes = Field(..., description="GitHub repository information")
    is_active: bool = Field(..., description="Whether the repository is active")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Update time")


class GitLabCodeRepositoryRes(BaseResponseData):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Code repository ID")
    provider: Literal["gitlab"] = Field(default="gitlab", description="Source control provider")
    repo_info: GitLabRepoInfoRes = Field(..., description="GitLab repository information")
    is_active: bool = Field(..., description="Whether the repository is active")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Update time")


CodeRepositoryRes = GitHubCodeRepositoryRes | GitLabCodeRepositoryRes


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
    repo_url: AnyHttpUrl | None = Field(default=None, description="Resolved repository URL")


ScmConnectionCreateReq = CodeRepositoryCreateReq
ScmConnectionRes = CodeRepositoryRes
ScmConnectionListRes = CodeRepositoryListRes
