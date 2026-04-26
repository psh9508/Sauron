from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from src.apis.models.AnalyzeRequest import (
    AnalyzeJobAcceptedRes,
    AnalyzeJobExistingRes,
    AnalyzeJobRes,
    AnalyzeRequest,
)
from src.apis.models.base_response_model import BaseResponseModel
from src.factories.analyze_job import get_analyze_job_service
from src.services.analyze_job_service import AnalyzeJobService

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("")
async def analyze(
    request: AnalyzeRequest,
    analyze_job_service: AnalyzeJobService = Depends(get_analyze_job_service),
) -> JSONResponse:
    result = await analyze_job_service.acreate_job(request)

    if isinstance(result, AnalyzeJobAcceptedRes):
        body = BaseResponseModel[AnalyzeJobAcceptedRes](data=result)
        return JSONResponse(content=body.model_dump(mode="json"), status_code=202)

    body = BaseResponseModel[AnalyzeJobExistingRes](data=result)
    return JSONResponse(content=body.model_dump(mode="json"), status_code=200)


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
