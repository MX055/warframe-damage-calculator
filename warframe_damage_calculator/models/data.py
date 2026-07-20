from collections.abc import ItemsView, Iterator, KeysView, Mapping, MutableMapping, ValuesView
from copy import deepcopy
from typing import ClassVar, Self, get_args, get_origin

from ..utils.types import DataValue
from .dist import Dist


class Data(MutableMapping[str, DataValue]):
    _fields: ClassVar[dict[str, object]] = {}
    _defaults: ClassVar[dict[str, DataValue]] = {}

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        cls._fields = dict(getattr(cls.__base__, "_fields", {}))
        cls._defaults = dict(getattr(cls.__base__, "_defaults", {}))

        for name, annotation in cls.__annotations__.items():
            if name.startswith("_") or get_origin(annotation) is ClassVar:
                continue

            cls._fields[name] = annotation

            if name in cls.__dict__:
                cls._defaults[name] = cls.__dict__[name]
                delattr(cls, name)

    def __init__(self, data: Mapping[str, DataValue] | None = None) -> None:
        object.__setattr__(self, "_values", {})
        object.__setattr__(self, "_default_values", {})
        object.__setattr__(self, "_suppressed_defaults", set())
        self.update(data or {})

    def __getitem__(self, key: str) -> DataValue:
        if key in self._values:
            return self._values[key]
        if key in self._suppressed_defaults or key not in self._defaults:
            raise KeyError(key)
        if key not in self._default_values:
            default = deepcopy(self._defaults[key])
            default = self._convert_field(key, default)
            if self._is_mutable(default):
                self._values[key] = default
                return default
            self._default_values[key] = default
        return self._default_values[key]

    def __setitem__(self, key: str, value: DataValue) -> None:
        self._suppressed_defaults.discard(key)
        self._default_values.pop(key, None)
        self._values[key] = self._convert_field(key, value)

    def __delitem__(self, key: str) -> None:
        if key in self._values:
            del self._values[key]
        elif key not in self._defaults or key in self._suppressed_defaults:
            raise KeyError(key)
        self._default_values.pop(key, None)
        if key in self._defaults:
            self._suppressed_defaults.add(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return repr(self.with_defaults())

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        copied = type(self).__new__(type(self))
        object.__setattr__(copied, "_values", {})
        object.__setattr__(copied, "_default_values", {})
        object.__setattr__(copied, "_suppressed_defaults", self._suppressed_defaults.copy())
        memo[id(self)] = copied
        copied.update(deepcopy(self._values, memo))
        object.__setattr__(copied, "_default_values", deepcopy(self._default_values, memo))
        return copied

    @staticmethod
    def _convert(value: DataValue) -> DataValue:
        if isinstance(value, Data): return value
        if isinstance(value, Mapping): return Data(value)
        if isinstance(value, list): return [Data._convert(item) for item in value]
        return value

    @staticmethod
    def _is_mutable(value: DataValue) -> bool:
        return isinstance(value, (Data, Dist, list, dict, set))

    @staticmethod
    def _convert_items(values: list[DataValue], item_type: object) -> list[DataValue]:
        if not isinstance(item_type, type) or not issubclass(item_type, Data):
            return [Data._convert(value) for value in values]

        items: list[DataValue] = []
        for value in values:
            if isinstance(value, item_type):
                items.append(value)
            elif isinstance(value, Mapping):
                items.append(item_type(value))
            else:
                items.append(value)
        return items

    @classmethod
    def _convert_field(cls, key: str, value: DataValue) -> DataValue:
        annotation = cls._fields.get(key)
        if annotation is Dist:
            return Dist(value)
        if isinstance(annotation, type) and issubclass(annotation, Data) and isinstance(value, Mapping):
            return value if isinstance(value, annotation) else annotation(value)
        if get_origin(annotation) is list and isinstance(value, list):
            return cls._convert_items(value, get_args(annotation)[0])
        return cls._convert(value)

    def __getattr__(self, key: str) -> DataValue:
        if key.startswith("_"):
            raise AttributeError(key)
        try: return self[key]
        except KeyError: raise AttributeError(key) from None

    def __setattr__(self, key: str, value: DataValue) -> None:
        self[key] = value

    def __delattr__(self, key: str) -> None:
        try: del self[key]
        except KeyError: raise AttributeError(key) from None

    def __contains__(self, key: object) -> bool:
        return key in self._values

    def keys(self) -> KeysView[str]:
        return self._values.keys()

    def values(self) -> ValuesView[DataValue]:
        return self._values.values()

    def items(self) -> ItemsView[str, DataValue]:
        return self._values.items()

    def __or__(self, other: Mapping[str, DataValue]) -> Self:
        merged = self.copy()
        merged.update(other)
        return merged

    def __ror__(self, other: Mapping[str, DataValue]) -> Self:
        merged = self.copy()
        explicit = merged._values
        object.__setattr__(merged, "_values", {})
        merged.update(other)
        merged.update(explicit)
        return merged

    def update(self, data: Mapping[str, DataValue], /) -> None:
        for key, value in data.items(): self[key] = value

    def copy(self) -> Self:
        return deepcopy(self)

    def with_defaults(self) -> dict[str, DataValue]:
        values = {key: self._convert_field(key, deepcopy(default)) for key, default in self._defaults.items() if key not in self._suppressed_defaults}
        values.update(deepcopy(self._values))
        return values
