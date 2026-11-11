"""Sentry-compatible ingest endpoint.

Lets any Sentry SDK report errors to Sauron. Configure the SDK with
``dsn="https://<repository_key>@<sauron-host>/<project_id>"``; ``project_id`` is
required by the DSN format but not used, since the repository key identifies the
repository.
"""

import logging

from fastapi import APIRouter, Depends, Query, Request

from src.factories.analyze_job import get_analyze_job_service
from src.services.analyze_job_service import AnalyzeJobService
from src.services.sentry_envelope_service import (
    decode_body,
    extract_sentry_key,
    parse_envelope,
    should_analyze,
    to_analyze_request,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sentry"])


@router.post("/{project_id}/envelope/")
@router.post("/{project_id}/envelope", include_in_schema=False)
async def ingest_envelope(
    project_id: str,  # Unused: the repository key identifies the repository; declared so OpenAPI documents the DSN path
    request: Request,
    sentry_key: str | None = None,
    analyze_job_service: AnalyzeJobService = Depends(get_analyze_job_service),
) -> dict:
    body = decode_body(await request.body(), request.headers.get("content-encoding"))
    envelope = parse_envelope(body)

    events = [event for event in envelope.events if should_analyze(event)]
    if events:
        repository_key = extract_sentry_key(
            auth_header=request.headers.get("x-sentry-auth"),
            query_key=sentry_key,
            envelope_headers=envelope.headers,
        )
        for event in events:
            await analyze_job_service.acreate_job(to_analyze_request(event, repository_key=repository_key))

    # Sentry SDKs only look at the status code; the body mirrors Sentry's for compatibility.
    return {"id": envelope.event_id}
