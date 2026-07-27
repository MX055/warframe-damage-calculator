"""Typed mapping containers that coerce plain dict values into Data subclasses."""

from collections.abc import Mapping
from typing import ClassVar

from ..core.data import Data
from ..utils.types import JsonValue


class TypedMapping(Data):
    _item_type: ClassVar[type[Data]]

    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, self._item_type): value = self._item_type(value)
        super().__setitem__(key, value)


class NamedTypedMapping(TypedMapping):
    """Like TypedMapping, but fills missing ``name`` from the map key."""

    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, self._item_type): value = self._item_type(value)
        if isinstance(value, self._item_type) and not getattr(value, "name", None): value.name = key
        Data.__setitem__(self, key, value)
