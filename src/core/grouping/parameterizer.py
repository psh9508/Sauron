import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParameterizationPattern:
    name: str
    pattern: str


# Order matters: more specific patterns must come before less specific ones.
# UUID before hex/int, float before int, etc.
DEFAULT_PATTERNS: list[ParameterizationPattern] = [
    ParameterizationPattern(
        name="uuid",
        pattern=r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
    ),
    ParameterizationPattern(
        name="email",
        pattern=r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+",
    ),
    ParameterizationPattern(
        name="url",
        pattern=r"(?:https?|ftp|wss?)://[^\s]+",
    ),
    ParameterizationPattern(
        name="ip",
        pattern=r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    ),
    ParameterizationPattern(
        name="date",
        pattern=r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?|\d{4}-[01]\d-[0-3]\d",
    ),
    ParameterizationPattern(
        name="hex",
        pattern=r"\b0[xX][0-9a-fA-F]+\b",
    ),
    ParameterizationPattern(
        name="float",
        pattern=r"-?\b\d+\.\d+\b",
    ),
    ParameterizationPattern(
        name="int",
        pattern=r"\b\d+\b",
    ),
]


class Parameterizer:
    def __init__(self, patterns: list[ParameterizationPattern] | None = None):
        patterns = patterns or DEFAULT_PATTERNS
        named_groups = [f"(?P<{p.name}>{p.pattern})" for p in patterns]
        self._combined_re = re.compile("|".join(named_groups))

    def parameterize(self, value: str) -> str:
        def _replace(match: re.Match[str]) -> str:
            group_name = match.lastgroup
            return f"<{group_name}>" if group_name else match.group(0)

        return self._combined_re.sub(_replace, value)


default_parameterizer = Parameterizer()
