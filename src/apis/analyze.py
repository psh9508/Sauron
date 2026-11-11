from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.apis.models.AnalyzeRequest import (
    AnalyzeJobRes,
    ErrorEventListRes,
)
from src.apis.models.base_response_model import BaseResponseModel
from src.factories.analyze_job import get_analyze_job_service
from src.services.analyze_job_service import AnalyzeJobService

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.get(
    "/errors",
    response_model=BaseResponseModel[ErrorEventListRes],
    status_code=status.HTTP_200_OK,
)
async def list_error_events(
    analyze_job_service: AnalyzeJobService = Depends(get_analyze_job_service),
) -> BaseResponseModel[ErrorEventListRes]:
    result = await analyze_job_service.alist_error_events()
    return BaseResponseModel[ErrorEventListRes](data=result)


@router.get(
    "/{job_id}",
    response_model=BaseResponseModel[AnalyzeJobRes],
    status_code=status.HTTP_200_OK,
)
async def get_analyze_job(
    job_id: UUID,
    analyze_job_service: AnalyzeJobService = Depends(get_analyze_job_service),
) -> BaseResponseModel[AnalyzeJobRes]:
    result = await analyze_job_service.aget_job(job_id)
    return BaseResponseModel[AnalyzeJobRes](data=result)
