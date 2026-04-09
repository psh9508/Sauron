from fastapi import APIRouter, Depends, status

from src.apis.models.base_response_model import BaseResponseModel
from src.apis.models.source_control import (
    CodeRepositoryCreateReq,
    CodeRepositoryListRes,
    CodeRepositoryRes,
)
from src.factories.source_control import get_source_control_service
from src.services.source_control_service import SourceControlService

router = APIRouter(prefix="/source_control", tags=["source_control"])


@router.post(
    "/repositories",
    response_model=BaseResponseModel[CodeRepositoryRes],
    status_code=status.HTTP_201_CREATED,
)
async def create_repository(
    request: CodeRepositoryCreateReq,
    source_control_service: SourceControlService = Depends(get_source_control_service),
) -> BaseResponseModel[CodeRepositoryRes]:
    result = await source_control_service.acreate_repository(request)
    return BaseResponseModel[CodeRepositoryRes](data=result)


@router.get(
    "/repositories",
    response_model=BaseResponseModel[CodeRepositoryListRes],
    status_code=status.HTTP_200_OK,
)
async def get_repositories(
    source_control_service: SourceControlService = Depends(get_source_control_service),
) -> BaseResponseModel[CodeRepositoryListRes]:
    result = await source_control_service.aget_repositories()
    return BaseResponseModel[CodeRepositoryListRes](data=result)
