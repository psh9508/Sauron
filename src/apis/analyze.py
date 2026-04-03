from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.apis.models.AnalyzeRequest import AnalyzeJobAcceptedRes, AnalyzeJobRes, AnalyzeRequest
from src.apis.models.base_response_model import BaseResponseModel
from src.factories.analyze_job import get_analyze_job_service
from src.services.analyze_job_service import AnalyzeJobService

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post(
    "",
    response_model=BaseResponseModel[AnalyzeJobAcceptedRes],
    status_code=status.HTTP_202_ACCEPTED,
)
async def analyze(
    request: AnalyzeRequest,
    analyze_job_service: AnalyzeJobService = Depends(get_analyze_job_service),
) -> BaseResponseModel[AnalyzeJobAcceptedRes]:
    result = await analyze_job_service.acreate_job(request)
    return BaseResponseModel[AnalyzeJobAcceptedRes](data=result)


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
