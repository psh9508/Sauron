"""Ingest Sentry SDK envelopes and convert them into Sauron analyze requests.

Any Sentry SDK pointed at a DSN of the form
``https://<repository_key>@<sauron-host>/<project_id>`` posts envelopes to
``/api/<project_id>/envelope/``. This module decodes those envelopes and maps each
error event onto ``AnalyzeCreateReq`` so the existing analyze pipeline handles it
unchanged.

Envelope format: https://develop.sentry.dev/sdk/data-model/envelopes/
"""

import json
import logging
import zlib
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import brotli
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from src.apis.models.AnalyzeRequest import AnalyzeCreateReq, EventDetail, StackFrame
from src.core.grouping import compute_fingerprint, compute_fingerprint_from_log
from src.services.exceptions.sentry_ingest_exception import (
    InvalidSentryEnvelopeError,
    SentryAuthMissingError,
    SentryEnvelopeTooLargeError,
    UnsupportedContentEncodingError,
)

logger = logging.getLogger(__name__)

# Matches Sentry's own envelope size limit.
MAX_ENVELOPE_BYTES = 20 * 1024 * 1024

# Events below this level (e.g. capture_message at "info") are not analyzed.
_ANALYZED_LEVELS = {"error", "fatal"}

_REPOSITORY_URL_TAG = "repository_url"
_GIT_COMMIT_SHA_TAG = "git_commit_sha"

_http_url_adapter = TypeAdapter(AnyHttpUrl)


@dataclass
class SentryEnvelope:
    headers: dict
    events: list[dict] = field(default_factory=list)

    @property
    def event_id(self) -> str | None:
        event_id = self.headers.get("event_id")
        if event_id:
            return event_id
        for event in self.events:
            if event.get("event_id"):
                return event["event_id"]
        return None


# ---------------------------------------------------------------------------
# Transport: body decoding, envelope parsing, auth
# ---------------------------------------------------------------------------


def decode_body(body: bytes, content_encoding: str | None) -> bytes:
    if len(body) > MAX_ENVELOPE_BYTES:
        raise SentryEnvelopeTooLargeError()

    encoding = (content_encoding or "").strip().lower()
    if encoding in ("", "identity"):
        return body
    try:
        if encoding == "gzip":
            return _zlib_decompress(body, wbits=16 + zlib.MAX_WBITS)
        if encoding == "deflate":
            try:
                return _zlib_decompress(body, wbits=zlib.MAX_WBITS)
            except zlib.error:
                # Some clients send raw deflate without the zlib header.
                return _zlib_decompress(body, wbits=-zlib.MAX_WBITS)
        if encoding == "br":
            return _brotli_decompress(body)
    except (zlib.error, brotli.error) as e:
        raise InvalidSentryEnvelopeError() from e
    raise UnsupportedContentEncodingError()


def _zlib_decompress(body: bytes, *, wbits: int) -> bytes:
    decompressor = zlib.decompressobj(wbits)
    data = decompressor.decompress(body, MAX_ENVELOPE_BYTES + 1)
    if len(data) > MAX_ENVELOPE_BYTES or decompressor.unconsumed_tail:
        raise SentryEnvelopeTooLargeError()
    return data


def _brotli_decompress(body: bytes) -> bytes:
    decompressor = brotli.Decompressor()
    data = decompressor.process(body, output_buffer_limit=MAX_ENVELOPE_BYTES + 1)
    if len(data) > MAX_ENVELOPE_BYTES:
        raise SentryEnvelopeTooLargeError()
    if not decompressor.is_finished():
        raise InvalidSentryEnvelopeError()  # truncated stream
    return data


def _read_line(data: bytes, pos: int) -> tuple[bytes, int]:
    end = data.find(b"\n", pos)
    if end == -1:
        return data[pos:], len(data)
    return data[pos:end], end + 1


def _load_json_object(raw: bytes) -> dict:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise InvalidSentryEnvelopeError() from e
    if not isinstance(value, dict):
        raise InvalidSentryEnvelopeError()
    return value


def parse_envelope(data: bytes) -> SentryEnvelope:
    header_line, pos = _read_line(data, 0)
    if not header_line.strip():
        raise InvalidSentryEnvelopeError()
    envelope = SentryEnvelope(headers=_load_json_object(header_line))

    while pos < len(data):
        item_header_line, pos = _read_line(data, pos)
        if not item_header_line.strip():
            continue  # tolerate blank lines / trailing newline
        item_header = _load_json_object(item_header_line)

        length = item_header.get("length")
        if isinstance(length, int) and length >= 0:
            if pos + length > len(data):
                raise InvalidSentryEnvelopeError()
            payload = data[pos : pos + length]
            pos += length
            if data[pos : pos + 1] == b"\n":
                pos += 1
        else:
            payload, pos = _read_line(data, pos)

        # Transactions, sessions, client reports, attachments etc. are not errors.
        if item_header.get("type") == "event":
            envelope.events.append(_load_json_object(payload))

    return envelope


def _parse_auth_header(value: str) -> dict[str, str]:
    value = value.strip()
    if value.lower().startswith("sentry "):
        value = value[len("sentry ") :]
    pairs: dict[str, str] = {}
    for part in value.split(","):
        key, sep, val = part.strip().partition("=")
        if sep:
            pairs[key.strip()] = val.strip()
    return pairs


def extract_sentry_key(
    *,
    auth_header: str | None,
    query_key: str | None,
    envelope_headers: dict,
) -> str:
    if auth_header:
        key = _parse_auth_header(auth_header).get("sentry_key")
        if key:
            return key
    if query_key:
        return query_key
    dsn = envelope_headers.get("dsn")
    if isinstance(dsn, str):
        key = urlsplit(dsn).username
        if key:
            return key
    raise SentryAuthMissingError()


# ---------------------------------------------------------------------------
# Event conversion
# ---------------------------------------------------------------------------


def _main_exception(event: dict) -> dict | None:
    exception = event.get("exception")
    values = exception.get("values") if isinstance(exception, dict) else exception
    if not isinstance(values, list):
        return None
    values = [v for v in values if isinstance(v, dict)]
    # Sentry orders chained exceptions oldest first; the last one is the exception that was raised.
    return values[-1] if values else None


def should_analyze(event: dict) -> bool:
    if _main_exception(event) is not None:
        return True
    return str(event.get("level") or "").lower() in _ANALYZED_LEVELS


def _convert_frames(stacktrace: object) -> list[dict]:
    if not isinstance(stacktrace, dict):
        return []
    raw_frames = stacktrace.get("frames")
    if not isinstance(raw_frames, list):
        return []

    frames: list[dict] = []
    for raw in raw_frames:
        if not isinstance(raw, dict):
            continue
        # filename is relative to the import root, so fingerprints stay stable across deploy paths
        # and match repository paths directly.
        lineno = raw.get("lineno")
        frame: dict = {
            "filename": raw.get("filename") or raw.get("abs_path") or raw.get("module") or "<unknown>",
            "lineno": lineno if isinstance(lineno, int) else 0,
            "function": raw.get("function") or "<unknown>",
        }
        context_line = raw.get("context_line")
        if isinstance(context_line, str) and context_line.strip():
            frame["code"] = context_line.strip()
        if isinstance(raw.get("in_app"), bool):
            frame["in_app"] = raw["in_app"]
        frames.append(frame)
    return frames


def _thread_frames(event: dict) -> list[dict]:
    """Stack attached to non-exception events (requires ``attach_stacktrace=True``)."""
    if isinstance(event.get("stacktrace"), dict):
        return _convert_frames(event["stacktrace"])
    threads = event.get("threads")
    values = threads.get("values") if isinstance(threads, dict) else threads
    if not isinstance(values, list):
        return []
    threads_with_stack = [t for t in values if isinstance(t, dict) and isinstance(t.get("stacktrace"), dict)]
    if not threads_with_stack:
        return []
    current = next((t for t in threads_with_stack if t.get("current") or t.get("crashed")), threads_with_stack[0])
    return _convert_frames(current["stacktrace"])


def _log_message(event: dict) -> tuple[str, str]:
    """Return (message template, formatted message)."""
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        template = logentry.get("message") or ""
        formatted = logentry.get("formatted") or template
        return str(template), str(formatted)
    message = event.get("message")
    if isinstance(message, dict):  # some SDKs send the logentry interface under "message"
        template = message.get("message") or ""
        return str(template), str(message.get("formatted") or template)
    text = str(message or "")
    return text, text


def _tags(event: dict) -> dict[str, str]:
    tags = event.get("tags")
    if isinstance(tags, dict):
        return {str(k): str(v) for k, v in tags.items() if v is not None}
    if isinstance(tags, list):
        return {str(t[0]): str(t[1]) for t in tags if isinstance(t, (list, tuple)) and len(t) == 2}
    return {}


def _breadcrumbs(event: dict) -> list[dict]:
    breadcrumbs = event.get("breadcrumbs")
    values = breadcrumbs.get("values") if isinstance(breadcrumbs, dict) else breadcrumbs
    if not isinstance(values, list):
        return []
    return [crumb for crumb in values if isinstance(crumb, dict)]


def _repository_url(tags: dict[str, str]) -> str | None:
    value = tags.get(_REPOSITORY_URL_TAG)
    if not value:
        return None
    try:
        _http_url_adapter.validate_python(value)
    except ValidationError:
        logger.warning("Ignoring malformed repository_url tag: %r", value)
        return None
    return value


def to_analyze_request(event: dict, *, repository_key: str) -> AnalyzeCreateReq:
    exception = _main_exception(event)
    if exception is not None:
        exc_type = str(exception.get("type") or "Error")
        exc_value = str(exception.get("value") or "")
        frames = _convert_frames(exception.get("stacktrace"))
        fingerprint = compute_fingerprint(exc_type, exc_value, frames)
    else:
        level = str(event.get("level") or "error").lower()
        exc_type = level.upper()
        template, exc_value = _log_message(event)
        frames = _thread_frames(event)
        fingerprint = compute_fingerprint_from_log(
            logger_name=str(event.get("logger") or ""),
            level=exc_type,
            message_template=template,
        )

    tags = _tags(event)
    return AnalyzeCreateReq(
        repository_key=repository_key,
        repository_url=_repository_url(tags),
        fingerprint=fingerprint,
        event=EventDetail(
            type=exc_type,
            value=exc_value,
            stacktrace=[StackFrame(**{k: v for k, v in f.items() if k != "in_app"}) for f in frames],
        ),
        breadcrumbs=_breadcrumbs(event),
        git_commit_sha=tags.get(_GIT_COMMIT_SHA_TAG) or event.get("release"),
    )
