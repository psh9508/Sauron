from dataclasses import dataclass
from uuid import UUID

from src.services.exceptions.app_base_error import AppBaseError


@dataclass
class AnalyzeJobNotFoundError(AppBaseError):
    job_id: UUID

    status_code = 404
    code = "AnalyzeJobNotFoundError"
    message = "Analyze job not found"
