from collections.abc import ItemsView, Iterator, KeysView, Mapping, MutableMapping, ValuesView
from copy import deepcopy
from typing import ClassVar, Self, get_args, get_origin

from ..utils.types import DataValue


class Data(MutableMapping[str, DataValue]):
    _fields: ClassVar[dict[str, object]] = {}
    _defaults: ClassVar[dict[str, DataValue]] = {}

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        fields: dict[str, object] = {}
        defaults: dict[str, DataValue] = {}
        for base in reversed(cls.__mro__[1:]):
            if issubclass(base, Data):
                fields.update(getattr(base, "_fields", {}))
                defaults.update(getattr(base, "_defaults", {}))

        for name, annotation in cls.__annotations__.items():
            if name.startswith("_") or get_origin(annotation) is ClassVar:
                continue
            fields[name] = annotation
            if name in cls.__dict__:
                defaults[name] = cls.__dict__[name]
                delattr(cls, name)

        cls._fields = fields
        cls._defaults = defaults

    def __init__(self, data: Mapping[str, DataValue] | None = None, /) -> None:
        object.__setattr__(self, "_values", {})
        self.update(deepcopy(self._defaults))
        if data is not None:
            self.update(data)

    def __getitem__(self, key: str) -> DataValue:
        return self._values[key]

    def __setitem__(self, key: str, value: DataValue) -> None:
        self._values[key] = self._convert(key, value)

    def __delitem__(self, key: str) -> None:
        del self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return repr(self.with_defaults())

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        copied = type(self).__new__(type(self))
        object.__setattr__(copied, "_values", {})
        memo[id(self)] = copied
        copied.update(deepcopy(self._values, memo))
        return copied

    def __getattr__(self, key: str) -> DataValue:
        if key.startswith("_"):
            raise AttributeError(key)
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None

    def __setattr__(self, key: str, value: DataValue) -> None:
        self[key] = value

    def __delattr__(self, key: str) -> None:
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key) from None

    def __contains__(self, key: object) -> bool:
        return key in self._values

    def __or__(self, other: Mapping[str, DataValue]) -> Self:
        merged = self.copy()
        merged.update(other)
        return merged

    def __ror__(self, other: Mapping[str, DataValue]) -> Self:
        merged = type(self)(other)
        merged.update(self)
        return merged

    @classmethod
    def _convert(cls, key: str, value: DataValue) -> DataValue:
        annotation = cls._fields.get(key)
        if isinstance(value, Data):
            return value
        if isinstance(annotation, type) and get_origin(annotation) is None and isinstance(value, Mapping):
            if issubclass(annotation, Data) or not issubclass(annotation, Mapping):
                return value if isinstance(value, annotation) else annotation(value)
        if get_origin(annotation) is list and isinstance(value, list):
            return cls._convert_items(value, get_args(annotation)[0])
        if isinstance(value, Mapping):
            return Data(value)
        if isinstance(value, list):
            return [cls._convert("", item) for item in value]
        return value

    @classmethod
    def _convert_items(cls, values: list[DataValue], item_type: object) -> list[DataValue]:
        if not isinstance(item_type, type) or not issubclass(item_type, Data):
            return [cls._convert("", value) for value in values]
        items: list[DataValue] = []
        for value in values:
            if isinstance(value, Data):
                items.append(value)
            elif isinstance(value, Mapping):
                items.append(item_type(value))
            else:
                items.append(value)
        return items

    def keys(self) -> KeysView[str]:
        return self._values.keys()

    def values(self) -> ValuesView[DataValue]:
        return self._values.values()

    def items(self) -> ItemsView[str, DataValue]:
        return self._values.items()

    def update(self, data: Mapping[str, DataValue] | None = None, /) -> None:
        if data is not None:
            for key, value in data.items():
                self[key] = value

    def copy(self) -> Self:
        return deepcopy(self)

    def with_defaults(self) -> dict[str, DataValue]:
        return deepcopy(self._values)
