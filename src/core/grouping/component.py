from __future__ import annotations

import hashlib
from collections.abc import Sequence


class GroupingComponent:
    def __init__(
        self,
        id: str,
        *,
        values: Sequence[str | GroupingComponent] | None = None,
        contributes: bool = True,
        hint: str | None = None,
    ):
        self.id = id
        self.values: Sequence[str | GroupingComponent] = values or []
        self.contributes = contributes
        self.hint = hint

    def iter_values(self) -> list[str]:
        if not self.contributes:
            return []
        result: list[str] = []
        for value in self.values:
            if isinstance(value, GroupingComponent):
                result.extend(value.iter_values())
            else:
                result.append(value)
        return result

    def get_hash(self) -> str | None:
        values = self.iter_values()
        if not values:
            return None
        h = hashlib.md5()
        for v in values:
            h.update(v.encode("utf-8"))
        return h.hexdigest()

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "contributes": self.contributes,
            "hint": self.hint,
            "values": [
                v.as_dict() if isinstance(v, GroupingComponent) else v
                for v in self.values
            ],
        }

    def __repr__(self) -> str:
        return (
            f"GroupingComponent(id={self.id!r}, contributes={self.contributes!r}, "
            f"hint={self.hint!r}, values={self.values!r})"
        )
