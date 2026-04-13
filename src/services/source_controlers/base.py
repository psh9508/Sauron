from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.services.source_control_models import IssuedAccessToken


@dataclass
class RepositoryInfo:
    """Provider-agnostic repository information."""
    owner: str
    repo_name: str
    default_branch: str | None = None


@dataclass
class FileContent:
    """Provider-agnostic file content response."""
    path: str
    content: str
    file_type: str = "file"


class SourceControlClient(ABC):
    """Abstract base class for source control providers.

    Implementations must provide methods for:
    - Token issuance (authentication)
    - Repository tree fetching
    - File content retrieval
    """

    @abstractmethod
    def issue_access_token(self, repo_url: str) -> IssuedAccessToken:
        """Issue an access token for the given repository."""
        raise NotImplementedError

    @abstractmethod
    def parse_repo_url(self, repo_url: str) -> RepositoryInfo:
        """Parse repository URL into owner and repo name."""
        raise NotImplementedError

    @abstractmethod
    def get_default_branch(self, access_token: str, repo_url: str) -> str:
        """Get the default branch of the repository."""
        raise NotImplementedError

    @abstractmethod
    def get_repository_tree(
        self,
        access_token: str,
        repo_url: str,
        branch: str | None = None,
    ) -> list[str]:
        """Get all file paths in the repository.

        Args:
            access_token: Access token for authentication
            repo_url: Repository URL
            branch: Branch name (uses default branch if None)

        Returns:
            List of file paths (blobs only, no directories)
        """
        raise NotImplementedError

    @abstractmethod
    def get_file_content(
        self,
        access_token: str,
        repo_url: str,
        file_path: str,
    ) -> FileContent:
        """Get content of a single file.

        Args:
            access_token: Access token for authentication
            repo_url: Repository URL
            file_path: Path to the file relative to repository root

        Returns:
            FileContent with path and decoded content
        """
        raise NotImplementedError

    @abstractmethod
    def build_repo_url(self, repo_info: dict[str, str]) -> str:
        """Build repository URL from repository info.

        Args:
            repo_info: Dictionary containing repository_name and base_url

        Returns:
            Full repository URL for this provider
        """
        raise NotImplementedError
