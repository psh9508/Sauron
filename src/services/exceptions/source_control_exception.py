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
    project_id: int

    status_code = 404
    code = "CodeRepositoryNotFoundError"
    message = "Code repository not found"


# Legacy alias for backwards compatibility
ScmConnectionNotFoundError = CodeRepositoryNotFoundError
