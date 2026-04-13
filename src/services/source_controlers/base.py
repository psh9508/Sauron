from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from src.services.source_control_models import IssuedAccessToken

if TYPE_CHECKING:
    from typing import Type


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

    @abstractmethod
    def validate_repo_info(self, repo_info: dict[str, str]) -> None:
        """Validate required fields in repo_info for this provider.

        Args:
            repo_info: Dictionary containing provider-specific repository info

        Raises:
            ValueError: If required fields are missing
        """
        raise NotImplementedError

    @abstractmethod
    def to_repo_info_response(self, repo_info: dict[str, str]) -> BaseModel:
        """Convert repo_info to response format, excluding sensitive data.

        Args:
            repo_info: Dictionary containing repository info with auth_config

        Returns:
            Provider-specific RepoInfoRes model for API response
        """
        raise NotImplementedError

    @abstractmethod
    def to_repository_response(
        self,
        id: int,
        repo_info: dict[str, str],
        is_active: bool,
        created_at: datetime,
        updated_at: datetime,
    ) -> BaseModel:
        """Convert repository data to full API response model.

        Args:
            id: Repository ID
            repo_info: Dictionary containing repository info
            is_active: Whether the repository is active
            created_at: Creation timestamp
            updated_at: Update timestamp

        Returns:
            Provider-specific CodeRepositoryRes model for API response
        """
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def build_repo_info_dict(
        repo_info: BaseModel,
        encrypted_auth_config: dict[str, str],
    ) -> dict[str, str]:
        """Build repo_info dictionary for database storage.

        Args:
            repo_info: Provider-specific RepoInfo request model
            encrypted_auth_config: Encrypted authentication configuration

        Returns:
            Dictionary to be stored in database
        """
        raise NotImplementedError

    @abstractmethod
    def resolve_repo_url(
        self,
        repository_id: int,
        repo_info: dict[str, str],
        repository_url: str | None,
    ) -> str:
        """Resolve and validate repository URL for this provider.

        Args:
            repository_id: Repository ID for error messages
            repo_info: Repository info from database
            repository_url: Optional repository URL from request

        Returns:
            Resolved repository URL

        Raises:
            Provider-specific exceptions for invalid configurations
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def create_client(
        cls,
        auth_config: dict[str, str],
        repo_url: str,
        base_url: str | None = None,
    ) -> "SourceControlClient":
        """Factory method to create a client instance.

        Args:
            auth_config: Decrypted authentication configuration
            repo_url: Repository URL
            base_url: Optional base URL for self-hosted instances

        Returns:
            Configured client instance
        """
        raise NotImplementedError


# Client registry for factory pattern
_CLIENT_REGISTRY: dict[str, type["SourceControlClient"]] = {}


def register_client(provider: str):
    """Decorator to register a source control client class."""
    def decorator(cls: type["SourceControlClient"]) -> type["SourceControlClient"]:
        _CLIENT_REGISTRY[provider.lower()] = cls
        return cls
    return decorator


def get_client_class(provider: str) -> type["SourceControlClient"]:
    """Get the client class for a provider."""
    from src.services.exceptions.source_control_exception import UnsupportedSourceControlProviderError

    normalized_provider = provider.strip().lower()
    client_class = _CLIENT_REGISTRY.get(normalized_provider)
    if client_class is None:
        raise UnsupportedSourceControlProviderError(provider=normalized_provider)
    return client_class


def create_source_control_client(
    provider: str,
    auth_config: dict[str, str],
    repo_url: str,
    base_url: str | None = None,
) -> "SourceControlClient":
    """Factory function to create a source control client."""
    client_class = get_client_class(provider)
    return client_class.create_client(auth_config, repo_url, base_url)
