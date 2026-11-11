"""Sentry envelope ingestion, driven by envelopes produced by the real sentry-sdk."""

import gzip
import json
import logging
import zlib
from dataclasses import asdict

import brotli
import pytest
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.transport import Transport

from src.apis.sentry_ingest import router
from src.core.grouping import compute_fingerprint, compute_fingerprint_from_log
from src.factories.analyze_job import get_analyze_job_service
from src.services import sentry_envelope_service as svc
from src.services.exceptions import AppBaseError
from src.services.exceptions.sentry_ingest_exception import (
    InvalidSentryEnvelopeError,
    SentryAuthMissingError,
    SentryEnvelopeTooLargeError,
    UnsupportedContentEncodingError,
)

REPOSITORY_KEY = "repo-public-key"
DSN = f"https://{REPOSITORY_KEY}@sauron.example.com/1"
SHA = "a" * 40


class CaptureTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.envelopes: list[bytes] = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope.serialize())


class FakeAnalyzeJobService:
    def __init__(self):
        self.requests = []

    async def acreate_job(self, create_req):
        self.requests.append(create_req)


@pytest.fixture
def transport():
    transport = CaptureTransport()
    sentry_sdk.init(
        dsn=DSN,
        transport=transport,
        release=SHA,
        default_integrations=False,
        integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
        attach_stacktrace=True,
    )
    sentry_sdk.set_tag("repository_url", "https://gitlab.example.com/group/repo")
    yield transport
    sentry_sdk.init()  # reset to a disabled client


@pytest.fixture
def service():
    return FakeAnalyzeJobService()


@pytest.fixture
def client(service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_analyze_job_service] = lambda: service

    @app.exception_handler(AppBaseError)
    async def _handler(_: Request, exc: AppBaseError):
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "data": asdict(exc)})

    return TestClient(app)


def _auth_header(key: str = REPOSITORY_KEY) -> dict[str, str]:
    return {"X-Sentry-Auth": f"Sentry sentry_key={key}, sentry_version=7, sentry_client=sentry.python/2.0"}


def _raise_value_error(user_id: int):
    raise ValueError(f"invalid user {user_id}")


# ---------------------------------------------------------------------------
# End-to-end through the HTTP endpoint
# ---------------------------------------------------------------------------


def test_exception_event_is_converted_and_queued(transport, client, service):
    sentry_sdk.add_breadcrumb(category="http", message="GET /api/users", level="info")
    try:
        _raise_value_error(42)
    except ValueError:
        sentry_sdk.capture_exception()

    [body] = transport.envelopes
    resp = client.post("/api/1/envelope/", content=body, headers=_auth_header())

    assert resp.status_code == 200
    assert resp.json()["id"]
    [req] = service.requests
    assert req.repository_key == REPOSITORY_KEY
    assert str(req.repository_url) == "https://gitlab.example.com/group/repo"
    assert req.git_commit_sha == SHA
    assert req.event.type == "ValueError"
    assert req.event.value == "invalid user 42"
    assert req.event_type == "exception"

    last = req.event.stacktrace[-1]
    assert last.function == "_raise_value_error"
    assert last.filename == "tests/test_sentry_ingest.py"
    assert last.code == 'raise ValueError(f"invalid user {user_id}")'
    assert "Traceback (most recent call last):" in req.stack_trace

    assert any(c.get("message") == "GET /api/users" and c.get("category") == "http" for c in req.breadcrumbs)


def test_same_error_with_different_values_groups_together(transport, client, service):
    for user_id in (1, 2):
        try:
            _raise_value_error(user_id)
        except ValueError:
            sentry_sdk.capture_exception()

    for body in transport.envelopes:
        assert client.post("/api/1/envelope/", content=body, headers=_auth_header()).status_code == 200

    first, second = service.requests
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 32


def test_chained_exception_uses_the_raised_one(transport, client, service):
    try:
        try:
            raise KeyError("missing")
        except KeyError as e:
            raise RuntimeError("wrapped") from e
    except RuntimeError:
        sentry_sdk.capture_exception()

    client.post("/api/1/envelope/", content=transport.envelopes[0], headers=_auth_header())
    [req] = service.requests
    assert req.event.type == "RuntimeError"
    assert req.event.value == "wrapped"


def test_error_log_without_exception(transport, client, service):
    logging.getLogger("billing").error("charge failed for order %s", 1234)

    [body] = transport.envelopes
    client.post("/api/1/envelope/", content=body, headers=_auth_header())

    [req] = service.requests
    assert req.event.type == "ERROR"
    assert req.event.value == "charge failed for order 1234"
    assert req.event.stacktrace  # from attach_stacktrace
    assert req.fingerprint == compute_fingerprint_from_log(
        logger_name="billing", level="ERROR", message_template="charge failed for order %s"
    )


def test_info_message_is_accepted_but_not_analyzed(transport, client, service):
    sentry_sdk.capture_message("just saying hi", level="info")

    resp = client.post("/api/1/envelope/", content=transport.envelopes[0])  # no auth needed when nothing is analyzed
    assert resp.status_code == 200
    assert service.requests == []


def test_gzip_and_brotli_bodies(transport, client, service):
    try:
        _raise_value_error(1)
    except ValueError:
        sentry_sdk.capture_exception()
    body = transport.envelopes[0]

    for encoding, compressed in (("gzip", gzip.compress(body)), ("br", brotli.compress(body))):
        resp = client.post(
            "/api/1/envelope/",
            content=compressed,
            headers={**_auth_header(), "Content-Encoding": encoding},
        )
        assert resp.status_code == 200, encoding
    assert len(service.requests) == 2


def test_key_from_query_string_and_missing_key(transport, client, service):
    try:
        _raise_value_error(1)
    except ValueError:
        sentry_sdk.capture_exception()
    # Strip the DSN from the envelope header so only the explicit sources remain.
    header, rest = transport.envelopes[0].split(b"\n", 1)
    headers = json.loads(header)
    headers.pop("dsn", None)
    body = json.dumps(headers).encode() + b"\n" + rest

    assert client.post("/api/1/envelope/", content=body).status_code == 401
    assert client.post(f"/api/1/envelope/?sentry_key={REPOSITORY_KEY}", content=body).status_code == 200
    assert service.requests[0].repository_key == REPOSITORY_KEY


def test_endpoint_without_trailing_slash(transport, client, service):
    try:
        _raise_value_error(1)
    except ValueError:
        sentry_sdk.capture_exception()
    assert client.post("/api/1/envelope", content=transport.envelopes[0], headers=_auth_header()).status_code == 200


# ---------------------------------------------------------------------------
# Unit-level edge cases
# ---------------------------------------------------------------------------


def test_parse_envelope_with_length_and_ignored_items():
    event = json.dumps({"event_id": "abc", "level": "error", "message": "x\ny"}).encode()
    session = b'{"sid":"1"}'
    data = (
        b'{"event_id":"abc"}\n'
        + json.dumps({"type": "session"}).encode() + b"\n" + session + b"\n"
        + json.dumps({"type": "event", "length": len(event)}).encode() + b"\n" + event
    )
    envelope = svc.parse_envelope(data)
    assert envelope.event_id == "abc"
    assert [e["event_id"] for e in envelope.events] == ["abc"]


@pytest.mark.parametrize("data", [b"", b"not json\n", b"{}\n{\"type\":\"event\",\"length\":100}\n{}"])
def test_parse_envelope_rejects_malformed(data):
    with pytest.raises(InvalidSentryEnvelopeError):
        svc.parse_envelope(data)


def test_decode_body_limits(monkeypatch):
    monkeypatch.setattr(svc, "MAX_ENVELOPE_BYTES", 1000)
    bomb = b"0" * 5000
    with pytest.raises(SentryEnvelopeTooLargeError):
        svc.decode_body(gzip.compress(bomb), "gzip")
    with pytest.raises(SentryEnvelopeTooLargeError):
        svc.decode_body(brotli.compress(bomb), "br")
    with pytest.raises(SentryEnvelopeTooLargeError):
        svc.decode_body(bomb, None)
    with pytest.raises(UnsupportedContentEncodingError):
        svc.decode_body(b"x", "zstd")
    with pytest.raises(InvalidSentryEnvelopeError):
        svc.decode_body(b"not gzip", "gzip")
    assert svc.decode_body(zlib.compress(b"hi"), "deflate") == b"hi"


def test_extract_sentry_key_from_envelope_dsn():
    assert svc.extract_sentry_key(auth_header=None, query_key=None, envelope_headers={"dsn": DSN}) == REPOSITORY_KEY
    with pytest.raises(SentryAuthMissingError):
        svc.extract_sentry_key(auth_header="Sentry sentry_version=7", query_key=None, envelope_headers={})


def test_malformed_release_and_repository_url_are_dropped():
    req = svc.to_analyze_request(
        {
            "exception": {"values": [{"type": "E", "value": "v"}]},
            "release": "myapp@1.2.3",
            "tags": [["repository_url", "not a url"]],
        },
        repository_key=REPOSITORY_KEY,
    )
    assert req.git_commit_sha is None
    assert req.repository_url is None


def test_in_app_flag_overrides_path_heuristic():
    frames = [
        {"filename": "/app/main.py", "function": "handler", "in_app": True},
        {"filename": "/app/vendored/lib.py", "function": "helper", "in_app": False},
    ]
    assert compute_fingerprint("E", "v", frames) == compute_fingerprint("E", "v", frames[:1])
