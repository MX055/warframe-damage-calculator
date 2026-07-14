from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from typing import Any, Self


def _restore_record(fields: dict[str, Any]) -> "Record":
    return Record(**fields)


class Record:
    __slots__ = ("dict",)

    def __init__(self, **fields: Any) -> None:
        object.__setattr__(self, "dict", dict(fields))

    def __getattr__(self, name: str) -> Any:
        return self.dict.get(name, None)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "dict":
            object.__setattr__(self, name, value)
        else:
            self.dict[name] = value

    def __delattr__(self, name: str) -> None:
        try:
            del self.dict[name]
        except KeyError:
            raise AttributeError(name) from None

    def __contains__(self, name: object) -> bool:
        return name in self.dict

    def __iter__(self) -> Iterator[str]:
        return iter(self.dict)

    def __len__(self) -> int:
        return len(self.dict)

    def __repr__(self) -> str:
        arguments = ", ".join(f"{name}={value!r}" for name, value in self.dict.items())
        return f"{type(self).__name__}({arguments})"

    @staticmethod
    def _fields(values: Record | Mapping[str, Any] | None) -> dict[str, Any]:
        if values is None:
            return {}
        if isinstance(values, Record):
            return values.dict
        return dict(values)

    def get(self, name: str, default: Any = None) -> Any:
        return self.dict.get(name, default)

    def keys(self):
        return self.dict.keys()

    def values(self):
        return self.dict.values()

    def items(self):
        return self.dict.items()

    def update(
        self,
        values: Record | Mapping[str, Any] | None = None,
        /,
        **fields: Any,
    ) -> None:
        self.dict.update(self._fields(values))
        self.dict.update(fields)

    def __or__(self, other: Record | Mapping[str, Any]) -> Self:
        if not isinstance(other, (Record, Mapping)):
            return NotImplemented
        return type(self)(**(self.dict | self._fields(other)))

    def __ror__(self, other: Record | Mapping[str, Any]) -> Self:
        if not isinstance(other, (Record, Mapping)):
            return NotImplemented
        return type(self)(**(self._fields(other) | self.dict))

    def __ior__(self, other: Record | Mapping[str, Any]) -> Self:
        if not isinstance(other, (Record, Mapping)):
            return NotImplemented
        self.update(other)
        return self

    def __reduce__(self):
        return _restore_record, (self.dict,)

    def __copy__(self) -> Self:
        return type(self)(**self.dict)

    def __deepcopy__(self, memo: dict[int, Any]) -> Self:
        copied = type(self)(**deepcopy(self.dict, memo))
        memo[id(self)] = copied
        return copied

    def copy(self) -> Self:
        return type(self)(**self.dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.dict)
