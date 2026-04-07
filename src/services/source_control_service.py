from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.apis.models.source_control import (
    AuthConfigRes,
    ProjectInfo,
    ScmConnectionCreateReq,
    ScmConnectionListRes,
    ScmConnectionRes,
    SourceControlAccessTokenRes,
)
from src.core.scm_pem_cipher import ScmAuthCipher
from src.repositories.scm_connection_repository import ScmConnectionRepository
from src.services.exceptions.source_control_exception import UnsupportedSourceControlProviderError
from src.services.source_controlers.base import SourceControlClient


class SourceControlService:
    def __init__(self, session: AsyncSession | None = None):
        self.scm_connection_repo = ScmConnectionRepository(session) if session is not None else None

    async def aget_connections(self) -> ScmConnectionListRes:
        if self.scm_connection_repo is None:
            raise RuntimeError("SCM connection repository is not initialized.")

        scm_connections = await self.scm_connection_repo.aget_all()
        return ScmConnectionListRes(
            connections=[
                self._to_connection_res(scm_connection)
                for scm_connection in scm_connections
            ]
        )

    async def issue_access_token(self, project_info: ProjectInfo) -> SourceControlAccessTokenRes:
        if self.scm_connection_repo is None:
            raise RuntimeError("SCM connection repository is not initialized.")

        scm_connection = await self.scm_connection_repo.aget_active_by_project_id(project_info.project_id)
        repo_url = self._build_repo_url(
            provider=scm_connection.provider,
            owner=scm_connection.owner,
            repo_name=scm_connection.repo_name,
        )

        decrypted_auth_config = ScmAuthCipher.decrypt_auth_config(scm_connection.auth_config)
        source_control_client = self._get_source_control_client(
            provider=scm_connection.provider,
            auth_config=decrypted_auth_config,
        )
        issued_token = source_control_client.issue_access_token(repo_url)

        return SourceControlAccessTokenRes(
            provider=scm_connection.provider,
            access_token=issued_token.access_token,
            expires_at=issued_token.expires_at,
            repo_url=repo_url,
        )

    async def acreate_connection(self, request: ScmConnectionCreateReq) -> ScmConnectionRes:
        if self.scm_connection_repo is None:
            raise RuntimeError("SCM connection repository is not initialized.")

        auth_config_dict = request.auth_config.model_dump()
        encrypted_auth_config = ScmAuthCipher.encrypt_auth_config(auth_config_dict)

        created_connection = await self.scm_connection_repo.acreate(
            project_id=request.project_id,
            provider=request.provider,
            owner=request.owner,
            repo_name=request.repo_name,
            auth_config=encrypted_auth_config,
        )

        return self._to_connection_res(created_connection)

    def _to_connection_res(self, scm_connection: Any) -> ScmConnectionRes:
        """Convert DB model to response model, excluding sensitive data."""
        auth_config = scm_connection.auth_config
        return ScmConnectionRes(
            project_id=scm_connection.project_id,
            provider=scm_connection.provider,
            owner=scm_connection.owner,
            repo_name=scm_connection.repo_name,
            auth_config=AuthConfigRes(type=auth_config.get("type", "unknown")),
            is_active=scm_connection.is_active,
            created_at=scm_connection.created_at,
            updated_at=scm_connection.updated_at,
        )

    def _get_source_control_client(
        self,
        provider: str,
        auth_config: dict[str, Any],
    ) -> SourceControlClient:
        selected_provider = provider.strip().lower()
        auth_type = auth_config.get("type")

        if selected_provider == "github" and auth_type == "github_app":
            from src.services.source_controlers.github_source_control import GitHubSourceControl

            return GitHubSourceControl(
                app_id=auth_config.get("app_id"),
                installation_id=auth_config.get("installation_id"),
                pem_contents=auth_config.get("pem"),
            )

        if selected_provider == "gitlab" and auth_type == "gitlab_pat":
            from src.services.source_controlers.gitlab_source_control import GitLabSourceControl

            return GitLabSourceControl(
                access_token=auth_config.get("access_token"),
            )

        raise UnsupportedSourceControlProviderError(provider=selected_provider)

    def _build_repo_url(self, provider: str, owner: str, repo_name: str) -> str:
        selected_provider = provider.strip().lower()

        if selected_provider == "github":
            return f"https://github.com/{owner}/{repo_name}"

        if selected_provider == "gitlab":
            return f"https://gitlab.com/{owner}/{repo_name}"

        raise UnsupportedSourceControlProviderError(provider=selected_provider)
