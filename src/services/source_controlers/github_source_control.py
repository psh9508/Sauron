import base64
import json
import os
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from src.apis.models.source_control import GitHubCodeRepositoryRes, GitHubRepoInfoCreate, GitHubRepoInfoRes
from src.core.jwt_logic import JwtLogic
from src.services.exceptions.source_control_exception import InvalidSourceControlRepositoryUrlError
from src.services.source_control_models import IssuedAccessToken
from src.services.source_controlers.base import FileContent, RepositoryInfo, SourceControlClient, register_client


@register_client("github")
class GitHubSourceControl(SourceControlClient):
    """GitHub source control client using GitHub App authentication."""

    API_BASE_URL = "https://api.github.com"
    API_VERSION = "2022-11-28"

    def __init__(
        self,
        app_id: str | None = None,
        installation_id: str | None = None,
        pem_contents: str | None = None,
    ) -> None:
        self.app_id = app_id or os.getenv("GITHUB_APP_ID")
        self.installation_id = installation_id or os.getenv("GITHUB_INSTALLATION_ID")
        self._raw_pem_contents = pem_contents or os.getenv("GITHUB_PEM")

    def issue_access_token(self, repo_url: str) -> IssuedAccessToken:
        github_app_jwt = JwtLogic.create_github_app_jwt(
            app_id=self._get_app_id(),
            private_key=self._get_pem_contents(),
        )
        request_body = json.dumps({
            "repositories": [self._extract_repository_name(repo_url)],
        }).encode("utf-8")

        request = Request(
            url=self._get_installation_access_token_url(),
            data=request_body,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_app_jwt}",
                "Content-Type": "application/json",
                "User-Agent": "Sauron",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Failed to issue GitHub installation access token: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Failed to reach GitHub for installation access token: {exc}") from exc

        access_token = payload.get("token")
        if not access_token:
            raise RuntimeError("GitHub response did not include an installation access token.")

        expires_at = payload.get("expires_at")
        return IssuedAccessToken(
            access_token=access_token,
            expires_at=self._parse_expires_at(expires_at),
        )

    def _get_app_id(self) -> str:
        if not self.app_id or self.app_id == "NONE":
            raise ValueError("GITHUB_APP_ID must be set.")

        return self.app_id

    def _get_installation_id(self) -> str:
        if not self.installation_id or self.installation_id == "NONE":
            raise ValueError("GITHUB_INSTALLATION_ID must be set.")

        return self.installation_id

    def _get_installation_access_token_url(self) -> str:
        installation_id = self._get_installation_id()
        return f"https://api.github.com/app/installations/{installation_id}/access_tokens"

    def _get_pem_contents(self) -> str:
        """Get and validate PEM contents. Only called when authentication is needed."""
        pem_contents = self._raw_pem_contents
        if not pem_contents or pem_contents == "NONE":
            raise ValueError("GITHUB_PEM must be set to PEM contents.")

        normalized_pem = pem_contents.replace("\\n", "\n").strip()
        if "BEGIN" not in normalized_pem or "PRIVATE KEY" not in normalized_pem:
            raise ValueError("GITHUB_PEM must contain a valid PEM private key.")

        return normalized_pem

    def _parse_expires_at(self, expires_at: str | None) -> datetime | None:
        if not expires_at:
            return None

        return datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

    def _extract_repository_name(self, repo_url: str) -> str:
        parsed_url = urlparse(repo_url)
        path_parts = [part for part in parsed_url.path.split("/") if part]

        if len(path_parts) < 2:
            raise InvalidSourceControlRepositoryUrlError(repo_url=repo_url)

        repository_name = path_parts[1]
        if repository_name.endswith(".git"):
            repository_name = repository_name[:-4]

        if not repository_name:
            raise InvalidSourceControlRepositoryUrlError(repo_url=repo_url)

        return repository_name

    def _get_headers(self, access_token: str) -> dict[str, str]:
        """Get standard GitHub API headers."""
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "X-GitHub-Api-Version": self.API_VERSION,
        }

    def _make_request(
        self,
        url: str,
        access_token: str,
        accept: str | None = None,
    ) -> dict:
        """Make a GET request to GitHub API."""
        headers = self._get_headers(access_token)
        if accept:
            headers["Accept"] = accept

        http_request = Request(url=url, headers=headers, method="GET")

        try:
            with urlopen(http_request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API request failed: {exc.code} {error_body}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Failed to connect to GitHub API: {exc.reason}"
            ) from exc

    def parse_repo_url(self, repo_url: str) -> RepositoryInfo:
        """Parse GitHub repository URL into owner and repo name."""
        parsed_url = urlparse(repo_url)
        path_parts = [part for part in parsed_url.path.strip("/").split("/") if part]

        if len(path_parts) < 2:
            raise InvalidSourceControlRepositoryUrlError(repo_url=repo_url)

        owner = path_parts[0]
        repo_name = path_parts[1].removesuffix(".git")

        if not owner or not repo_name:
            raise InvalidSourceControlRepositoryUrlError(repo_url=repo_url)

        return RepositoryInfo(owner=owner, repo_name=repo_name)

    def get_default_branch(self, access_token: str, repo_url: str) -> str:
        """Get the default branch of the GitHub repository."""
        repo_info = self.parse_repo_url(repo_url)
        url = f"{self.API_BASE_URL}/repos/{repo_info.owner}/{repo_info.repo_name}"

        response = self._make_request(url, access_token)
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
        """Get all file paths in the GitHub repository."""
        repo_info = self.parse_repo_url(repo_url)

        if branch is None:
            branch = self.get_default_branch(access_token, repo_url)

        encoded_branch = quote(branch, safe="")
        url = (
            f"{self.API_BASE_URL}/repos/{repo_info.owner}/{repo_info.repo_name}"
            f"/git/trees/{encoded_branch}?recursive=1"
        )

        response = self._make_request(url, access_token)
        tree_items = response.get("tree", [])

        if not isinstance(tree_items, list):
            raise RuntimeError("Repository tree response did not include a valid tree")

        return [
            item["path"]
            for item in tree_items
            if isinstance(item, dict)
            and item.get("type") == "blob"
            and isinstance(item.get("path"), str)
        ]

    def get_file_content(
        self,
        access_token: str,
        repo_url: str,
        file_path: str,
    ) -> FileContent:
        """Get content of a single file from GitHub repository."""
        repo_info = self.parse_repo_url(repo_url)
        normalized_path = file_path.strip().lstrip("/")

        if not normalized_path:
            raise RuntimeError("A repository path is required.")

        encoded_path = quote(normalized_path, safe="/")
        url = (
            f"{self.API_BASE_URL}/repos/{repo_info.owner}/{repo_info.repo_name}"
            f"/contents/{encoded_path}"
        )

        response = self._make_request(
            url,
            access_token,
            accept="application/vnd.github.object+json",
        )

        content = response.get("content", "")
        encoding = response.get("encoding")

        if encoding == "base64" and content:
            decoded_content = base64.b64decode(content).decode("utf-8", errors="replace")
        else:
            decoded_content = content

        return FileContent(
            path=response.get("path", normalized_path),
            content=decoded_content,
            file_type=response.get("type", "file"),
        )

    def build_repo_url(self, repo_info: dict[str, str]) -> str:
        """Build GitHub repository URL from repository_name."""
        repository_name = repo_info.get("repository_name")

        if not repository_name:
            raise ValueError("'repository_name' is required to build GitHub repo URL.")

        return f"https://github.com/{repository_name.lstrip('/')}"

    def validate_repo_info(self, repo_info: dict[str, str]) -> None:
        """Validate required fields for GitHub repository."""
        if not repo_info.get("repository_name"):
            raise ValueError("'repository_name' is required for GitHub provider.")

    def to_repo_info_response(self, repo_info: dict[str, str]) -> GitHubRepoInfoRes:
        """Convert repo_info to response format for GitHub."""
        return GitHubRepoInfoRes(
            repository_name=repo_info.get("repository_name", ""),
        )

    def to_repository_response(
        self,
        id: int,
        repo_info: dict[str, str],
        is_active: bool,
        created_at: datetime,
        updated_at: datetime,
    ) -> GitHubCodeRepositoryRes:
        """Convert repository data to GitHubCodeRepositoryRes."""
        return GitHubCodeRepositoryRes(
            id=id,
            provider="github",
            repo_info=self.to_repo_info_response(repo_info),
            is_active=is_active,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def build_repo_info_dict(
        repo_info: GitHubRepoInfoCreate,
        encrypted_auth_config: dict[str, str],
    ) -> dict[str, str]:
        """Build repo_info dictionary for GitHub repository."""
        return {
            "repository_name": repo_info.repository_name,
            "auth_config": encrypted_auth_config,
        }

    def resolve_repo_url(
        self,
        repository_id: int,
        repo_info: dict[str, str],
        repository_url: str | None,
    ) -> str:
        """Resolve repository URL for GitHub (ignores repository_url parameter)."""
        repository_name = repo_info.get("repository_name")
        if not repository_name:
            raise InvalidSourceControlRepositoryUrlError(repo_url="missing repository_name")
        return f"https://github.com/{repository_name.lstrip('/')}"

    @classmethod
    def create_client(
        cls,
        auth_config: dict[str, str],
        repo_url: str,
        base_url: str | None = None,
    ) -> "GitHubSourceControl":
        """Factory method to create GitHubSourceControl instance."""
        return cls(
            app_id=auth_config.get("app_id"),
            installation_id=auth_config.get("installation_id"),
            pem_contents=auth_config.get("pem"),
        )
