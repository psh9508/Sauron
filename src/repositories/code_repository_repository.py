from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.schemas.code_repository import CodeRepository
from src.services.exceptions.source_control_exception import (
    DuplicateCodeRepositoryError,
    CodeRepositoryNotFoundError,
)


class CodeRepositoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def aget_all(self) -> list[CodeRepository]:
        stmt = select(CodeRepository).order_by(CodeRepository.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def acreate(
        self,
        provider: str,
        repo_info: dict[str, Any],
    ) -> CodeRepository:
        try:
            stmt = insert(CodeRepository).values(
                provider=provider,
                repo_info=repo_info,
            ).returning(CodeRepository)

            result = await self.session.execute(stmt)
            return result.scalar_one()
        except IntegrityError as exc:
            raise DuplicateCodeRepositoryError() from exc

    async def aget_active_by_project_id(self, project_id: int) -> CodeRepository:
        stmt = select(CodeRepository).where(
            CodeRepository.repo_info["project_id"].as_integer() == project_id,
            CodeRepository.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        code_repository = result.scalar_one_or_none()

        if code_repository is None:
            raise CodeRepositoryNotFoundError(project_id=project_id)

        return code_repository
