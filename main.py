import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.config import get_settings
from src.apis.analyze import router as analyze_router
from src.apis.source_control import router as source_control_router
from src.core.database import init_db_session
from src.core.job_worker import AnalyzeJobWorker
from src.services.exceptions import AppBaseError

settings = get_settings()

@asynccontextmanager
async def lifespan(_: FastAPI):
    worker: AnalyzeJobWorker | None = None
    worker_task: asyncio.Task | None = None

    if settings.db is not None:
        init_db_session()
        worker = AnalyzeJobWorker(initialize_db=False)
        worker_task = asyncio.create_task(worker.arun())

    yield

    if worker is not None:
        await worker.astop()
    if worker_task is not None:
        await worker_task


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analyze_router)
app.include_router(source_control_router)


@app.exception_handler(AppBaseError)
async def app_base_error_handler(_: Request, exc: AppBaseError):
    error_data = asdict(exc)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": error_data,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8002)
