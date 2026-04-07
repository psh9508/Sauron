from datetime import datetime
from typing import Annotated, Any, Literal, Union

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


class ScmConnectionCreateReq(BaseModel):
    project_id: int = Field(..., description="Project ID")
    provider: Literal["github", "gitlab"] = Field(..., description="Source control provider")
    owner: str = Field(..., description="Repository owner")
    repo_name: str = Field(..., description="Repository name")
    auth_config: AuthConfig = Field(..., description="Authentication configuration")


class ProjectInfo(BaseModel):
    project_id: int = Field(..., description="Project ID")


class AuthConfigRes(BaseModel):
    type: str = Field(..., description="Auth type (github_app, gitlab_pat)")


class ScmConnectionRes(BaseResponseData):
    model_config = ConfigDict(from_attributes=True)

    project_id: int = Field(..., description="Project ID")
    provider: Literal["github", "gitlab"] = Field(..., description="Source control provider")
    owner: str = Field(..., description="Repository owner")
    repo_name: str = Field(..., description="Repository name")
    auth_config: AuthConfigRes = Field(..., description="Auth config (sensitive data excluded)")
    is_active: bool = Field(..., description="Whether the connection is active")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Update time")


class ScmConnectionListRes(BaseResponseData):
    connections: list[ScmConnectionRes] = Field(
        default_factory=list,
        description="SCM connection list",
    )


class SourceControlAccessTokenRes(BaseResponseData):
    provider: Literal["github", "gitlab"] = Field(..., description="Source control provider")
    access_token: str = Field(..., description="Access token for the source control provider")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_at: datetime | None = Field(default=None, description="Token expiration time")
    repo_url: AnyHttpUrl = Field(..., description="Repository URL of the project")
