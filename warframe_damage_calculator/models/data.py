from __future__ import annotations

from ..utils.types import JsonScalar, JsonValue
from .dist import Dist

type DataValue = JsonScalar | Data | Dist | list[DataValue]

DISTRIBUTIONS = {"damage", "forced_procs", "explosion_damage", "explosion_forced_procs"}


class Data(dict[str, DataValue]):
    def __init__(self, data: dict[str, JsonValue] | None = None) -> None:
        super().__init__()
        self.update(data or {})

    @classmethod
    def _convert(cls, key: str, value: JsonValue | DataValue) -> DataValue:
        if isinstance(value, Data): return value
        if isinstance(value, dict): return cls._distribution(value) if key in DISTRIBUTIONS else cls(value)
        if isinstance(value, list): return [cls._convert(key, item) for item in value]
        return value

    @classmethod
    def _distribution(cls, value: JsonValue | DataValue) -> DataValue:
        if "value" not in value: return Dist(value)
        return cls(value | {"value": Dist(value["value"])})

    def __getattr__(self, key: str) -> DataValue:
        try: return self[key]
        except KeyError: raise AttributeError(key) from None

    def __setattr__(self, key: str, value: JsonValue | DataValue) -> None:
        self[key] = value

    def __delattr__(self, key: str) -> None:
        try: del self[key]
        except KeyError: raise AttributeError(key) from None

    def __setitem__(self, key: str, value: JsonValue | DataValue) -> None:
        dict.__setitem__(self, key, self._convert(key, value))

    def __or__(self, other: dict[str, JsonValue] | Data) -> Data:
        return Data(dict(self) | dict(other))

    def __ror__(self, other: dict[str, JsonValue]) -> Data:
        return Data(other | dict(self))
    
    def update(self, data: dict[str, JsonValue] | Data) -> None:
        for key, value in data.items():
            self[key] = value

    def copy(self) -> Data:
        return Data(self)
