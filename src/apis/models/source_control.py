from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from src.apis.models.base_response_model import BaseResponseData


# Auth config types for different providers
class GitHubAppAuthConfig(BaseModel):
    type: Literal["github_app"] = Field(default="github_app", description="Auth type")
    app_id: str = Field(..., description="GitHub App ID")
    installation_id: str = Field(..., description="GitHub Installation ID")
    pem: str = Field(..., description="GitHub App private key PEM contents")


class GitLabPatAuthConfig(BaseModel):
    type: Literal["gitlab_pat"] = Field(default="gitlab_pat", description="Auth type")
    access_token: str = Field(..., description="GitLab Personal Access Token")


AuthConfig = Annotated[
    Union[GitHubAppAuthConfig, GitLabPatAuthConfig],
    Field(discriminator="type"),
]


class RepoInfo(BaseModel):
    owner: str = Field(..., description="Repository owner")
    repo_name: str = Field(..., description="Repository name")
    auth_config: AuthConfig = Field(..., description="Authentication configuration")


class CodeRepositoryCreateReq(BaseModel):
    provider: Literal["github", "gitlab"] = Field(..., description="Source control provider")
    repo_info: RepoInfo = Field(..., description="Repository information")


class AuthConfigRes(BaseModel):
    type: str = Field(..., description="Auth type (github_app, gitlab_pat)")


class RepoInfoRes(BaseModel):
    owner: str = Field(..., description="Repository owner")
    repo_name: str = Field(..., description="Repository name")
    auth_config: AuthConfigRes = Field(..., description="Auth config (sensitive data excluded)")


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
