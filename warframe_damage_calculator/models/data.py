from copy import deepcopy
from typing import Any

type DataValue = Any


class Data(dict[str, DataValue]):
    def __init__(self, data: dict[str, DataValue] | None = None) -> None:
        super().__init__()
        self.update(data or {})

    @classmethod
    def _convert(cls, value: DataValue) -> DataValue:
        if isinstance(value, Data): return value
        if isinstance(value, dict): return cls(value)
        if isinstance(value, list): return [cls._convert(item) for item in value]
        return value

    def __getattr__(self, key: str) -> DataValue:
        try: return self[key]
        except KeyError: raise AttributeError(key) from None

    def __setattr__(self, key: str, value: DataValue) -> None:
        self[key] = value

    def __delattr__(self, key: str) -> None:
        try: del self[key]
        except KeyError: raise AttributeError(key) from None

    def __setitem__(self, key: str, value: DataValue) -> None:
        dict.__setitem__(self, key, self._convert(value))

    def __or__(self, other: dict[str, DataValue]) -> Data:
        return Data(dict(self) | dict(other))

    def __ror__(self, other: dict[str, DataValue]) -> Data:
        return Data(other | dict(self))
    
    def update(self, data: dict[str, DataValue]) -> None:
        for key, value in data.items():
            self[key] = value

    def copy(self) -> Data:
        return deepcopy(self)
