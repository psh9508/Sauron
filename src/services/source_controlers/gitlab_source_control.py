import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from src.apis.models.source_control import GitLabCodeRepositoryRes, GitLabRepoInfoCreate, GitLabRepoInfoRes
from src.services.exceptions.source_control_exception import (
    GitLabRepositoryUrlHostMismatchError,
    GitLabRepositoryUrlRequiredError,
    InvalidGitLabRepositoryConfigurationError,
    InvalidSourceControlRepositoryUrlError,
)
from src.services.source_control_models import IssuedAccessToken
from src.services.source_controlers.base import FileContent, RepositoryInfo, SourceControlClient, register_client


@register_client("gitlab")
class GitLabSourceControl(SourceControlClient):
    """GitLab source control client using Personal Access Token (PAT).

    GitLab API automatically uses HEAD (latest commit on default branch)
    when ref parameter is not specified, ensuring we always get the latest code.
    """

    def __init__(self, access_token: str, repo_url: str, base_url: str | None = None) -> None:
        self.access_token = access_token
        self.repo_url = repo_url
        self.base_url = base_url.rstrip("/") if base_url else self._extract_base_url(repo_url)
        self.API_BASE_URL = f"{self.base_url}/api/v4"

    def _extract_base_url(self, repo_url: str) -> str:
        """Extract base URL from repository URL.

        Example: https://git.nwz.kr/ntech/ai/project -> https://git.nwz.kr
        """
        parsed = urlparse(repo_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def issue_access_token(self, repo_url: str) -> IssuedAccessToken:
        """
        For GitLab PAT, we simply return the stored access token.
        PATs don't have a built-in expiration tracking mechanism via API,
        so we return None for expires_at.
        """
        return IssuedAccessToken(
            access_token=self.access_token,
            expires_at=None,
        )

    def _get_headers(self) -> dict[str, str]:
        """Get standard GitLab API headers."""
        return {
            "PRIVATE-TOKEN": self.access_token,
            "Content-Type": "application/json",
        }

    def _make_request(self, url: str, raw: bool = False) -> dict | str | list:
        """Make a GET request to GitLab API."""
        headers = self._get_headers()
        http_request = Request(url=url, headers=headers, method="GET")

        try:
            with urlopen(http_request, timeout=30) as response:
                content = response.read().decode("utf-8")
                if raw:
                    return content
                return json.loads(content)
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitLab API request failed: {exc.code} {error_body}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Failed to connect to GitLab API: {exc.reason}"
            ) from exc

    def parse_repo_url(self, repo_url: str) -> RepositoryInfo:
        """Parse GitLab repository URL into owner and repo name."""
        parsed_url = urlparse(repo_url)
        path_parts = [part for part in parsed_url.path.strip("/").split("/") if part]

        if len(path_parts) < 2:
            raise InvalidSourceControlRepositoryUrlError(repo_url=repo_url)

        # GitLab supports nested groups, so owner could be "group/subgroup"
        # For simplicity, we treat the last part as repo_name and rest as owner
        repo_name = path_parts[-1].removesuffix(".git")
        owner = "/".join(path_parts[:-1])

        if not owner or not repo_name:
            raise InvalidSourceControlRepositoryUrlError(repo_url=repo_url)

        return RepositoryInfo(owner=owner, repo_name=repo_name)

    def _get_project_path(self, repo_url: str) -> str:
        """Get URL-encoded project path for GitLab API."""
        repo_info = self.parse_repo_url(repo_url)
        project_path = f"{repo_info.owner}/{repo_info.repo_name}"
        return quote(project_path, safe="")

    def get_default_branch(self, access_token: str, repo_url: str) -> str:
        """Get the default branch of the GitLab repository."""
        project_path = self._get_project_path(repo_url)
        url = f"{self.API_BASE_URL}/projects/{project_path}"

        response = self._make_request(url)
        if not isinstance(response, dict):
            raise RuntimeError("Unexpected response from GitLab API")

        default_branch = response.get("default_branch")

        if not isinstance(default_branch, str) or not default_branch:
            raise RuntimeError("Repository metadata did not include default_branch")

        return default_branch

    def get_repository_tree(
        self,
        access_token: str,
        repo_url: str,
        branch: str | None = None,
    ) -> list[str]:
        """Get all file paths in the GitLab repository.

        When branch is None, GitLab API automatically uses the default branch,
        ensuring we always get the latest file structure.
        """
        project_path = self._get_project_path(repo_url)

        # GitLab paginates tree results, we need to fetch all pages
        all_files: list[str] = []
        page = 1
        per_page = 100

        while True:
            # ref is omitted - GitLab uses default branch automatically
            url = (
                f"{self.API_BASE_URL}/projects/{project_path}/repository/tree"
                f"?recursive=true&per_page={per_page}&page={page}"
            )

            # Add ref only if explicitly specified
            if branch:
                url += f"&ref={quote(branch, safe='')}"

            response = self._make_request(url)
            if not isinstance(response, list):
                raise RuntimeError("Repository tree response did not include a valid tree")

            if not response:
                break

            for item in response:
                if isinstance(item, dict) and item.get("type") == "blob":
                    path = item.get("path")
                    if isinstance(path, str):
                        all_files.append(path)

            if len(response) < per_page:
                break

            page += 1

        return all_files

    def get_file_content(
        self,
        access_token: str,
        repo_url: str,
        file_path: str,
    ) -> FileContent:
        """Get content of a single file from GitLab repository.

        Uses HEAD (latest commit on default branch) automatically when
        ref parameter is not specified.
        """
        project_path = self._get_project_path(repo_url)
        normalized_path = file_path.strip().lstrip("/")

        if not normalized_path:
            raise RuntimeError("A repository path is required.")

        # GitLab requires URL-encoding for file paths
        encoded_path = quote(normalized_path, safe="")

        # ref is omitted - GitLab uses HEAD (default branch) automatically
        url = (
            f"{self.API_BASE_URL}/projects/{project_path}"
            f"/repository/files/{encoded_path}/raw"
        )

        content = self._make_request(url, raw=True)
        if not isinstance(content, str):
            raise RuntimeError("Unexpected response from GitLab API")

        return FileContent(
            path=normalized_path,
            content=content,
            file_type="file",
        )

    def build_repo_url(self, repo_info: dict[str, str]) -> str:
        """Build GitLab repository URL using base_url and repository_name."""
        base_url = repo_info.get("base_url") or self.base_url
        repository_name = repo_info.get("repository_name")

        if not base_url:
            raise ValueError("'base_url' is required to build GitLab repo URL.")
        if not repository_name:
            raise ValueError("'repository_name' is required to build GitLab repo URL.")

        return f"{base_url.rstrip('/')}/{repository_name.lstrip('/')}"

    def validate_repo_info(self, repo_info: dict[str, str]) -> None:
        """Validate required fields for GitLab repository."""
        if not repo_info.get("base_url"):
            raise ValueError("'base_url' is required for GitLab provider.")
        if not repo_info.get("repository_name"):
            raise ValueError("'repository_name' is required for GitLab provider.")

    def to_repo_info_response(self, repo_info: dict[str, str]) -> GitLabRepoInfoRes:
        """Convert repo_info to response format for GitLab."""
        return GitLabRepoInfoRes(
            base_url=repo_info.get("base_url", ""),
        )

    def to_repository_response(
        self,
        id: int,
        repo_info: dict[str, str],
        is_active: bool,
        created_at: datetime,
        updated_at: datetime,
    ) -> GitLabCodeRepositoryRes:
        """Convert repository data to GitLabCodeRepositoryRes."""
        return GitLabCodeRepositoryRes(
            id=id,
            provider="gitlab",
            repo_info=self.to_repo_info_response(repo_info),
            is_active=is_active,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def build_repo_info_dict(
        repo_info: GitLabRepoInfoCreate,
        encrypted_auth_config: dict[str, str],
    ) -> dict[str, str]:
        """Build repo_info dictionary for GitLab repository."""
        return {
            "base_url": str(repo_info.base_url).rstrip("/"),
            "auth_config": encrypted_auth_config,
        }

    def resolve_repo_url(
        self,
        repository_id: int,
        repo_info: dict[str, str],
        repository_url: str | None,
    ) -> str:
        """Resolve and validate repository URL for GitLab."""
        base_url = repo_info.get("base_url")
        if not isinstance(base_url, str) or not base_url:
            raise InvalidGitLabRepositoryConfigurationError(repository_id=repository_id)

        if repository_url is None:
            raise GitLabRepositoryUrlRequiredError(repository_id=repository_id)

        return self._validate_repository_url(
            repository_id=repository_id,
            repository_url=repository_url,
            base_url=base_url,
        )

    def _validate_repository_url(
        self,
        repository_id: int,
        repository_url: str,
        base_url: str,
    ) -> str:
        """Validate GitLab repository URL against base_url."""
        parsed_repo_url = urlparse(repository_url)
        parsed_base_url = urlparse(base_url)

        if not parsed_repo_url.scheme or not parsed_repo_url.netloc:
            raise InvalidSourceControlRepositoryUrlError(repo_url=repository_url)
        if parsed_repo_url.query or parsed_repo_url.fragment:
            raise InvalidSourceControlRepositoryUrlError(repo_url=repository_url)

        if (
            parsed_repo_url.scheme.lower(),
            parsed_repo_url.netloc.lower(),
        ) != (
            parsed_base_url.scheme.lower(),
            parsed_base_url.netloc.lower(),
        ):
            raise GitLabRepositoryUrlHostMismatchError(
                repository_id=repository_id,
                repository_url=repository_url,
                base_url=base_url,
            )

        normalized_path = parsed_repo_url.path.rstrip("/")
        if normalized_path.endswith(".git"):
            normalized_path = normalized_path[:-4]
        if not normalized_path.strip("/"):
            raise InvalidSourceControlRepositoryUrlError(repo_url=repository_url)

        return f"{parsed_repo_url.scheme}://{parsed_repo_url.netloc}{normalized_path}"

    @classmethod
    def create_client(
        cls,
        auth_config: dict[str, str],
        repo_url: str,
        base_url: str | None = None,
    ) -> "GitLabSourceControl":
        """Factory method to create GitLabSourceControl instance."""
        return cls(
            access_token=auth_config.get("access_token"),
            repo_url=repo_url,
            base_url=base_url,
        )
