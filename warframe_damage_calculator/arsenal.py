from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from importlib.resources import files
from pathlib import Path
from typing import Generic, Self, TypeVar

from .domain.enemies import Enemy
from .domain.upgrades import Upgrade
from .domain.weapons import Melee, Primary, Secondary, Weapon
from .schema import validate_database


T = TypeVar("T", Weapon, Upgrade, Enemy)


def _key(value: str) -> str:
    return " ".join(value.split()).casefold()


class Repository(Generic[T]):
    __slots__ = ("_records", "_factory", "_index")

    def __init__(self, records: Mapping[str, Mapping], factory: Callable[[Mapping], T]) -> None:
        self._records = dict(records)
        self._factory = factory
        self._index = {_key(name): name for name in records}

    def get(self, name: str) -> T:
        try: record = self._records[self._index[_key(name)]]
        except KeyError: raise KeyError(name) from None
        return self._factory(record)

    def __iter__(self) -> Iterator[str]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._records, key=str.casefold))


def _weapon(record: Mapping) -> Weapon:
    category = record["type"]
    cls = Primary if category in {"primary", "archgun"} else Secondary if category == "secondary" else Melee if category == "melee" else None
    if cls is None: raise ValueError(f"unsupported weapon type {category!r}")
    return cls.from_record(record)


class Arsenal:
    __slots__ = ("database", "weapon", "upgrade", "enemy")

    def __init__(self, database: Mapping) -> None:
        self.database = dict(database)
        validate_database(self.database)
        self.weapon = Repository(self.database["weapons"], _weapon)
        self.upgrade = Repository(self.database["upgrades"], Upgrade.from_record)
        self.enemy = Repository(self.database["enemies"], lambda record: Enemy.from_record(record, loaded=True))

    @classmethod
    def from_file(cls, path: str | Path) -> Self:
        with Path(path).open(encoding="utf-8") as stream: return cls(json.load(stream))

    @classmethod
    def bundled(cls) -> Self:
        resource = files("warframe_damage_calculator.database").joinpath("database.json")
        with resource.open(encoding="utf-8") as stream: return cls(json.load(stream))


arsenal = Arsenal.bundled()
