from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any


class Runtime:
    __slots__ = ("_allowed", "_values")

    def __init__(self, allowed: Iterable[str], values: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_allowed", frozenset(allowed))
        unknown = set(values) - self._allowed
        if unknown: raise TypeError(f"unknown runtime fields: {', '.join(sorted(unknown))}")
        object.__setattr__(self, "_values", dict(values))

    def __getattr__(self, name: str) -> Any:
        try: return self._values[name]
        except KeyError: raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        if name not in self._allowed: raise TypeError(f"unknown runtime field {name!r}")
        self._values[name] = value

    def set(self, **values: Any) -> None:
        unknown = set(values) - self._allowed
        if unknown: raise TypeError(f"unknown runtime fields: {', '.join(sorted(unknown))}")
        self._values.update(values)

    def copy(self) -> Runtime:
        return Runtime(self._allowed, deepcopy(self._values))

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self._values)
