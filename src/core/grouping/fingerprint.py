"""Error grouping fingerprints for ingested Sentry events.

A frame may carry Sentry's ``in_app`` flag, which takes precedence over the
path-based heuristic.
"""

import hashlib

from src.core.grouping.component import GroupingComponent
from src.core.grouping.parameterizer import default_parameterizer


def is_user_frame(frame: dict) -> bool:
    in_app = frame.get("in_app")
    if isinstance(in_app, bool):
        return in_app

    filename = frame.get("filename", "")
    if "site-packages" in filename:
        return False
    if "lib/python" in filename:
        return False
    if filename.startswith("<"):
        return False
    return True


def _build_frame_component(frame: dict) -> GroupingComponent:
    contributes = is_user_frame(frame)
    hint = None if contributes else "ignored because frame is not user code"

    return GroupingComponent(
        id="frame",
        values=[
            GroupingComponent(id="filename", values=[frame.get("filename", "")]),
            GroupingComponent(id="function", values=[frame.get("function", "")]),
        ],
        contributes=contributes,
        hint=hint,
    )


def _build_stacktrace_component(frames: list[dict]) -> GroupingComponent:
    if not frames:
        return GroupingComponent(id="stacktrace", values=[], contributes=False, hint="no frames available")

    frame_components = [_build_frame_component(f) for f in frames]

    if not any(fc.contributes for fc in frame_components):
        for fc in frame_components:
            fc.contributes = True
            fc.hint = "included because no user frames were found"

    return GroupingComponent(id="stacktrace", values=frame_components)


def _build_exception_component(
    exception_type: str,
    exception_value: str,
    frames: list[dict],
) -> GroupingComponent:
    type_component = GroupingComponent(id="type", values=[exception_type])

    parameterized_value = default_parameterizer.parameterize(exception_value)
    value_component = GroupingComponent(id="value", values=[parameterized_value])

    stacktrace_component = _build_stacktrace_component(frames)

    if stacktrace_component.contributes:
        value_component.contributes = False
        value_component.hint = "ignored because stacktrace takes precedence"

    return GroupingComponent(
        id="exception",
        values=[type_component, value_component, stacktrace_component],
    )


def _fallback_hash(seed: str) -> str:
    return hashlib.md5(seed.encode("utf-8")).hexdigest()


def compute_fingerprint(exception_type: str, exception_value: str, frames: list[dict]) -> str:
    component = _build_exception_component(exception_type, exception_value, frames)
    return component.get_hash() or _fallback_hash(exception_type)


def compute_fingerprint_from_log(logger_name: str, level: str, message_template: str) -> str:
    parameterized = default_parameterizer.parameterize(message_template)

    component = GroupingComponent(
        id="log_message",
        values=[
            GroupingComponent(id="logger", values=[logger_name]),
            GroupingComponent(id="level", values=[level]),
            GroupingComponent(id="message", values=[parameterized]),
        ],
    )
    return component.get_hash() or _fallback_hash(f"{logger_name}:{level}")
