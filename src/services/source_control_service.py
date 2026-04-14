from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.apis.models.AnalyzeRequest import AnalyzeRequest
from src.apis.models.source_control import (
    CodeRepositoryCreateReqPayload,
    CodeRepositoryListRes,
    CodeRepositoryRes,
    SourceControlAccessTokenRes,
)
from src.core.scm_pem_cipher import ScmAuthCipher
from src.repositories.code_repository_repository import CodeRepositoryRepository
from src.services.exceptions.source_control_exception import SourceControlProviderMismatchError
from src.services.source_controlers.base import (
    FileContent,
    SourceControlClient,
    create_source_control_client,
    get_client_class,
)

# Import clients to trigger registration
import src.services.source_controlers.github_source_control  # noqa: F401
import src.services.source_controlers.gitlab_source_control  # noqa: F401


class SourceControlService:
    def __init__(self, session: AsyncSession | None = None):
        self.code_repo_repository = CodeRepositoryRepository(session) if session is not None else None

    async def aget_repositories(self) -> CodeRepositoryListRes:
        code_repositories = await self._require_repository_repo().aget_all()
        return CodeRepositoryListRes(
            repositories=[self._to_repository_res(code_repo) for code_repo in code_repositories]
        )

    async def acreate_repository(self, request: CodeRepositoryCreateReqPayload) -> CodeRepositoryRes:
        repo_repository = self._require_repository_repo()
        auth_config_dict = request.repo_info.auth_config.model_dump()
        encrypted_auth_config = ScmAuthCipher.encrypt_auth_config(request.provider, auth_config_dict)

        # Delegate repo_info_dict creation to client
        client_class = get_client_class(request.provider)
        repo_info_dict = client_class.build_repo_info_dict(request.repo_info, encrypted_auth_config)

        created_repo = await repo_repository.acreate(
            provider=request.provider,
            repo_info=repo_info_dict,
        )
        return self._to_repository_res(created_repo)

    async def avalidate_analyze_request(self, request: AnalyzeRequest) -> None:
        """Validate analyze request by resolving provider from DB."""
        code_repo = await self._get_active_repository(request.repository_id)

        # Delegate URL validation to client
        client = create_source_control_client(
            provider=code_repo.provider,
            auth_config={},
            repo_url="",
        )
        client.resolve_repo_url(
            repository_id=code_repo.id,
            repo_info=code_repo.repo_info,
            repository_url=str(request.repository_url) if request.repository_url is not None else None,
        )

    async def issue_access_token(
        self,
        repository_id: int,
        provider: str | None = None,
        repository_url: str | None = None,
    ) -> SourceControlAccessTokenRes:
        client, issued_access_token, repo_url, resolved_provider = await self._get_repository_access(
            repository_id=repository_id,
            provider=provider,
            repository_url=repository_url,
        )
        return SourceControlAccessTokenRes(
            provider=resolved_provider,
            access_token=issued_access_token.access_token,
            expires_at=issued_access_token.expires_at,
            repo_url=repo_url,
        )

    async def get_client_for_repository(
        self,
        repository_id: int,
        provider: str | None = None,
        repository_url: str | None = None,
    ) -> tuple[SourceControlClient, str, str]:
        client, issued_access_token, repo_url, _ = await self._get_repository_access(
            repository_id=repository_id,
            provider=provider,
            repository_url=repository_url,
        )
        return client, issued_access_token.access_token, repo_url

    async def get_repository_tree(
        self,
        repository_id: int,
        branch: str | None = None,
        provider: str | None = None,
        repository_url: str | None = None,
    ) -> list[str]:
        client, access_token, repo_url = await self.get_client_for_repository(
            repository_id=repository_id,
            provider=provider,
            repository_url=repository_url,
        )
        return client.get_repository_tree(access_token, repo_url, branch)

    async def get_file_content(
        self,
        repository_id: int,
        file_path: str,
        provider: str | None = None,
        repository_url: str | None = None,
    ) -> FileContent:
        client, access_token, repo_url = await self.get_client_for_repository(
            repository_id=repository_id,
            provider=provider,
            repository_url=repository_url,
        )
        return client.get_file_content(access_token, repo_url, file_path)

    async def get_multiple_file_contents(
        self,
        repository_id: int,
        file_paths: list[str],
        provider: str | None = None,
        repository_url: str | None = None,
    ) -> list[FileContent]:
        client, access_token, repo_url = await self.get_client_for_repository(
            repository_id=repository_id,
            provider=provider,
            repository_url=repository_url,
        )

        contents: list[FileContent] = []
        for file_path in file_paths:
            content = client.get_file_content(access_token, repo_url, file_path)
            contents.append(content)

        return contents

    async def _get_repository_access(
        self,
        repository_id: int,
        provider: str | None,
        repository_url: str | None,
    ):
        code_repo = await self._get_active_repository(repository_id)
        resolved_provider = code_repo.provider.strip().lower()
        if provider is not None:
            self._validate_provider_match(provider, resolved_provider)

        decrypted_auth_config = ScmAuthCipher.decrypt_auth_config(
            resolved_provider,
            code_repo.repo_info.get("auth_config", {}),
        )

        # Delegate URL resolution to client
        client = create_source_control_client(
            provider=resolved_provider,
            auth_config=decrypted_auth_config,
            repo_url="",
            base_url=code_repo.repo_info.get("base_url"),
        )

        repo_url = client.resolve_repo_url(
            repository_id=code_repo.id,
            repo_info=code_repo.repo_info,
            repository_url=repository_url,
        )

        issued_access_token = client.issue_access_token(repo_url)
        return client, issued_access_token, repo_url, resolved_provider

    async def _get_active_repository(self, repository_id: int):
        return await self._require_repository_repo().aget_active_by_id(repository_id)

    def _require_repository_repo(self) -> CodeRepositoryRepository:
        if self.code_repo_repository is None:
            raise RuntimeError("Code repository is not initialized.")
        return self.code_repo_repository

    def _to_repository_res(self, code_repo: Any) -> CodeRepositoryRes:
        provider = code_repo.provider.strip().lower()

        # Delegate full response creation to client
        client = create_source_control_client(
            provider=provider,
            auth_config={},
            repo_url="",
        )
        return client.to_repository_response(
            id=code_repo.id,
            repo_info=code_repo.repo_info,
            is_active=code_repo.is_active,
            created_at=code_repo.created_at,
            updated_at=code_repo.updated_at,
        )

    def _validate_provider_match(self, request_provider: str, repository_provider: str) -> None:
        normalized_request_provider = request_provider.strip().lower()
        normalized_repository_provider = repository_provider.strip().lower()
        if normalized_request_provider != normalized_repository_provider:
            raise SourceControlProviderMismatchError(
                request_provider=normalized_request_provider,
                repository_provider=normalized_repository_provider,
            )
