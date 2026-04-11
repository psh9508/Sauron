from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.apis.models.source_control import (
    AuthConfigRes,
    CodeRepositoryCreateReq,
    CodeRepositoryListRes,
    CodeRepositoryRes,
    RepoInfoRes,
    SourceControlAccessTokenRes,
)
from src.core.scm_pem_cipher import ScmAuthCipher
from src.repositories.code_repository_repository import CodeRepositoryRepository
from src.services.exceptions.source_control_exception import UnsupportedSourceControlProviderError
from src.services.source_controlers.base import FileContent, SourceControlClient


class SourceControlService:
    def __init__(self, session: AsyncSession | None = None):
        self.code_repo_repository = CodeRepositoryRepository(session) if session is not None else None

    async def aget_repositories(self) -> CodeRepositoryListRes:
        if self.code_repo_repository is None:
            raise RuntimeError("Code repository is not initialized.")

        code_repositories = await self.code_repo_repository.aget_all()
        return CodeRepositoryListRes(
            repositories=[
                self._to_repository_res(code_repo)
                for code_repo in code_repositories
            ]
        )

    async def issue_access_token(self, repository_id: int) -> SourceControlAccessTokenRes:
        if self.code_repo_repository is None:
            raise RuntimeError("Code repository is not initialized.")

        code_repo = await self.code_repo_repository.aget_active_by_id(repository_id)
        repo_info = code_repo.repo_info
        repo_url = self._build_repo_url(
            provider=code_repo.provider,
            owner=repo_info.get("owner"),
            repo_name=repo_info.get("repo_name"),
        )

        decrypted_auth_config = ScmAuthCipher.decrypt_auth_config(repo_info.get("auth_config", {}))
        source_control_client = self._get_source_control_client(
            provider=code_repo.provider,
            auth_config=decrypted_auth_config,
        )
        issued_token = source_control_client.issue_access_token(repo_url)

        return SourceControlAccessTokenRes(
            provider=code_repo.provider,
            access_token=issued_token.access_token,
            expires_at=issued_token.expires_at,
            repo_url=repo_url,
        )

    async def acreate_repository(self, request: CodeRepositoryCreateReq) -> CodeRepositoryRes:
        if self.code_repo_repository is None:
            raise RuntimeError("Code repository is not initialized.")

        repo_info = request.repo_info
        auth_config_dict = repo_info.auth_config.model_dump()
        encrypted_auth_config = ScmAuthCipher.encrypt_auth_config(auth_config_dict)

        repo_info_dict = {
            "owner": repo_info.owner,
            "repo_name": repo_info.repo_name,
            "auth_config": encrypted_auth_config,
        }

        created_repo = await self.code_repo_repository.acreate(
            provider=request.provider,
            repo_info=repo_info_dict,
        )

        return self._to_repository_res(created_repo)

    def _to_repository_res(self, code_repo: Any) -> CodeRepositoryRes:
        """Convert DB model to response model, excluding sensitive data."""
        repo_info = code_repo.repo_info
        auth_config = repo_info.get("auth_config", {})

        return CodeRepositoryRes(
            id=code_repo.id,
            provider=code_repo.provider,
            repo_info=RepoInfoRes(
                owner=repo_info.get("owner"),
                repo_name=repo_info.get("repo_name"),
                auth_config=AuthConfigRes(type=auth_config.get("type", "unknown")),
            ),
            is_active=code_repo.is_active,
            created_at=code_repo.created_at,
            updated_at=code_repo.updated_at,
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

    async def get_client_for_repository(self, repository_id: int) -> tuple[SourceControlClient, str, str]:
        """Get a source control client for the given repository.

        Args:
            repository_id: The ID of the repository

        Returns:
            Tuple of (client, access_token, repo_url)
        """
        if self.code_repo_repository is None:
            raise RuntimeError("Code repository is not initialized.")

        code_repo = await self.code_repo_repository.aget_active_by_id(repository_id)
        repo_info = code_repo.repo_info
        repo_url = self._build_repo_url(
            provider=code_repo.provider,
            owner=repo_info.get("owner"),
            repo_name=repo_info.get("repo_name"),
        )

        decrypted_auth_config = ScmAuthCipher.decrypt_auth_config(repo_info.get("auth_config", {}))
        client = self._get_source_control_client(
            provider=code_repo.provider,
            auth_config=decrypted_auth_config,
        )

        issued_token = client.issue_access_token(repo_url)

        return client, issued_token.access_token, repo_url

    async def get_repository_tree(self, repository_id: int, branch: str | None = None) -> list[str]:
        """Get all file paths in the repository.

        Args:
            repository_id: The ID of the repository
            branch: Optional branch name (uses default branch if None)

        Returns:
            List of file paths
        """
        client, access_token, repo_url = await self.get_client_for_repository(repository_id)
        return client.get_repository_tree(access_token, repo_url, branch)

    async def get_file_content(self, repository_id: int, file_path: str) -> FileContent:
        """Get content of a single file from the repository.

        Args:
            repository_id: The ID of the repository
            file_path: Path to the file relative to repository root

        Returns:
            FileContent with path and decoded content
        """
        client, access_token, repo_url = await self.get_client_for_repository(repository_id)
        return client.get_file_content(access_token, repo_url, file_path)

    async def get_multiple_file_contents(
        self,
        repository_id: int,
        file_paths: list[str],
    ) -> list[FileContent]:
        """Get content of multiple files from the repository.

        Args:
            repository_id: The ID of the repository
            file_paths: List of file paths relative to repository root

        Returns:
            List of FileContent objects
        """
        client, access_token, repo_url = await self.get_client_for_repository(repository_id)

        contents: list[FileContent] = []
        for file_path in file_paths:
            content = client.get_file_content(access_token, repo_url, file_path)
            contents.append(content)

        return contents
