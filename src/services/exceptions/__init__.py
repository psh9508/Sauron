from src.services.exceptions.analyze_job_exception import AnalyzeJobNotFoundError
from src.services.exceptions.app_base_error import AppBaseError
from src.services.exceptions.source_control_exception import (
    CodeRepositoryNotFoundError,
    DuplicateCodeRepositoryError,
    # Legacy aliases
    DuplicateScmConnectionError,
    InvalidSourceControlEncryptionKeyError,
    InvalidSourceControlRepositoryUrlError,
    ScmConnectionNotFoundError,
    SourceControlEncryptionKeyNotConfiguredError,
    UnsupportedSourceControlProviderError,
)

__all__ = [
    "AnalyzeJobNotFoundError",
    "AppBaseError",
    "CodeRepositoryNotFoundError",
    "DuplicateCodeRepositoryError",
    # Legacy aliases
    "DuplicateScmConnectionError",
    "InvalidSourceControlEncryptionKeyError",
    "InvalidSourceControlRepositoryUrlError",
    "ScmConnectionNotFoundError",
    "SourceControlEncryptionKeyNotConfiguredError",
    "UnsupportedSourceControlProviderError",
]
