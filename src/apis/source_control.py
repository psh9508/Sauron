from fastapi import APIRouter, Depends, status

from src.apis.models.base_response_model import BaseResponseModel
from src.apis.models.source_control import (
    ProjectInfo,
    ScmConnectionCreateReq,
    ScmConnectionRes,
    SourceControlAccessTokenRes,
)
from src.factories.source_control import get_source_control_service
from src.services.source_control_service import SourceControlService

router = APIRouter(prefix="/source_control", tags=["source_control"])


@router.post(
    "/connections",
    response_model=BaseResponseModel[ScmConnectionRes],
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    request: ScmConnectionCreateReq,
    source_control_service: SourceControlService = Depends(get_source_control_service),
) -> BaseResponseModel[ScmConnectionRes]:
    result = await source_control_service.acreate_connection(request)
    return BaseResponseModel[ScmConnectionRes](data=result)
    