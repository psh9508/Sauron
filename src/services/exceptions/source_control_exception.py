from dataclasses import dataclass

from src.services.exceptions.app_base_error import AppBaseError


@dataclass
class UnsupportedSourceControlProviderError(AppBaseError):
    provider: str

    status_code = 400
    code = "UnsupportedSourceControlProviderError"
    message = "Unsupported source control provider"


@dataclass
class InvalidSourceControlRepositoryUrlError(AppBaseError):
    repo_url: str

    status_code = 400
    code = "InvalidSourceControlRepositoryUrlError"
    message = "Invalid repository URL for source control provider"


@dataclass
class SourceControlProviderMismatchError(AppBaseError):
    request_provider: str
    repository_provider: str

    status_code = 400
    code = "SourceControlProviderMismatchError"
    message = "Analyze request provider does not match repository provider"


@dataclass
class GitLabRepositoryUrlRequiredError(AppBaseError):
    repository_id: int

    status_code = 400
    code = "GitLabRepositoryUrlRequiredError"
    message = "GitLab analyze requests require repository_url"


@dataclass
class GitLabRepositoryUrlHostMismatchError(AppBaseError):
    repository_id: int
    repository_url: str
    base_url: str

    status_code = 400
    code = "GitLabRepositoryUrlHostMismatchError"
    message = "GitLab repository_url host does not match configured base_url"


@dataclass
class InvalidGitLabRepositoryConfigurationError(AppBaseError):
    repository_id: int

    status_code = 500
    code = "InvalidGitLabRepositoryConfigurationError"
    message = "GitLab repository configuration is invalid"


@dataclass
class DuplicateCodeRepositoryError(AppBaseError):
    status_code = 409
    code = "DuplicateCodeRepositoryError"
    message = "Code repository already exists"


# Legacy alias for backwards compatibility
DuplicateScmConnectionError = DuplicateCodeRepositoryError


@dataclass
class SourceControlEncryptionKeyNotConfiguredError(AppBaseError):
    status_code = 500
    code = "SourceControlEncryptionKeyNotConfiguredError"
    message = "SCM PEM encryption key is not configured"


@dataclass
class InvalidSourceControlEncryptionKeyError(AppBaseError):
    status_code = 500
    code = "InvalidSourceControlEncryptionKeyError"
    message = "SCM PEM encryption key is invalid"


@dataclass
class CodeRepositoryNotFoundError(AppBaseError):
    repository_id: int

    status_code = 404
    code = "CodeRepositoryNotFoundError"
    message = "Code repository not found"
