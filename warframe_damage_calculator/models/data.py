from collections.abc import Mapping
from typing import Any, Self

from .dist import Dist


DISTRIBUTIONS = {"damage", "forced_procs", "explosion_damage", "explosion_forced_procs"}


class Data(dict[str, Any]):
    def __init__(self, data: Mapping[str, Any] | None = None) -> None:
        super().__init__()
        self.update(data or {})

    @classmethod
    def _convert(cls, key: str, value: Any) -> Any:
        if key in DISTRIBUTIONS:
            if isinstance(value, list):
                return [cls._distribution(item) for item in value]
            return cls._distribution(value)
        if isinstance(value, Mapping) and not isinstance(value, (Data, Dist)):
            return cls(value)
        if isinstance(value, (list, tuple)):
            return type(value)(cls._convert("", item) for item in value)
        return value.copy() if isinstance(value, Data) else value

    @classmethod
    def _distribution(cls, value: Any) -> Any:
        if isinstance(value, Dist) or not isinstance(value, Mapping):
            return value
        if "value" not in value:
            return Dist(value)
        effect = cls(value)
        if isinstance(effect.value, Mapping):
            effect.value = Dist(effect.value)
        return effect

    def __getattr__(self, key: str) -> Any:
        return self.get(key)

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def __delattr__(self, key: str) -> None:
        try: del self[key]
        except KeyError: raise AttributeError(key) from None

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, self._convert(key, value))

    def update(self, data: Mapping[str, Any] | tuple = (), /, **values: Any) -> None:
        values = dict(data, **values)
        for key, value in values.items(): self[key] = value

    def copy(self) -> Self:
        return type(self)(self)

    def __or__(self, other: Mapping[str, Any]) -> Self:
        return type(self)(dict(self) | dict(other))

    def __ror__(self, other: Mapping[str, Any]) -> Self:
        return type(self)(dict(other) | dict(self))
