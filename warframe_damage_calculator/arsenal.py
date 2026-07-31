from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from importlib.resources import files
from pathlib import Path
from typing import Generic, Self, TypeVar, cast

from .domain.enemies import Enemy
from .domain.perks import Perk
from .domain.upgrades import Upgrade
from .domain.weapons import Melee, Primary, Secondary, Weapon
from .schema import validate_database


type ArsenalWeapon = Primary | Secondary | Melee
T = TypeVar("T", Weapon, Upgrade, Enemy, Perk)


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


def _weapon(record: Mapping, perks: Mapping[str, Perk]) -> ArsenalWeapon:
    category = record["type"]
    cls = Primary if category in {"primary", "archgun"} else Secondary if category == "secondary" else Melee if category == "melee" else None
    if cls is None: raise ValueError(f"unsupported weapon type {category!r}")
    return cls.from_record(record, perks)


class WeaponRepository(Repository[Weapon]):
    def get(self, name: str) -> ArsenalWeapon:
        return cast(ArsenalWeapon, super().get(name))


class Arsenal:
    __slots__ = ("database", "weapon", "mod", "arcane", "perk", "enemy")

    def __init__(self, database: Mapping) -> None:
        self.database: dict = dict(database)
        validate_database(self.database)
        perk_definitions = {name: Perk.from_record(record) for name, record in self.database["perks"].items()}
        self.weapon = WeaponRepository(self.database["weapons"], lambda record: _weapon(record, perk_definitions))
        self.mod = Repository[Upgrade](self.database["mods"], lambda record: Upgrade.from_record(record, kind="mod"))
        self.arcane = Repository[Upgrade](self.database["arcanes"], lambda record: Upgrade.from_record(record, kind="arcane"))
        self.perk = Repository[Perk](self.database["perks"], Perk.from_record)
        self.enemy = Repository[Enemy](self.database["enemies"], lambda record: Enemy.from_record(record, loaded=True))

    @classmethod
    def from_file(cls, path: str | Path) -> Self:
        with Path(path).open(encoding="utf-8") as stream: return cls(json.load(stream))

    @classmethod
    def bundled(cls) -> Self:
        resource = files("warframe_damage_calculator.database").joinpath("database.json")
        with resource.open(encoding="utf-8") as stream: return cls(json.load(stream))


class _LazyArsenal:
    __slots__ = ("_loaded",)

    def __init__(self) -> None:
        self._loaded: Arsenal | None = None

    def _get(self) -> Arsenal:
        if self._loaded is None: self._loaded = Arsenal.bundled()
        return self._loaded

    @property
    def database(self) -> dict:
        return self._get().database

    @property
    def weapon(self) -> WeaponRepository:
        return self._get().weapon

    @property
    def mod(self) -> Repository[Upgrade]:
        return self._get().mod

    @property
    def arcane(self) -> Repository[Upgrade]:
        return self._get().arcane

    @property
    def perk(self) -> Repository[Perk]:
        return self._get().perk

    @property
    def enemy(self) -> Repository[Enemy]:
        return self._get().enemy


arsenal = _LazyArsenal()
