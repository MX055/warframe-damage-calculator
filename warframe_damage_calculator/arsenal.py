from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from importlib.resources import files
from pathlib import Path
from typing import Generic, Self, TypeVar

from .domain.enemies import Enemy
from .domain.upgrades import Perk
from .domain.upgrades import Arcane, Mod, Upgrade
from .domain.weapons import Archgun, Melee, Primary, Secondary, Weapon
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


class Arsenal:
    __slots__ = ("database", "primary", "secondary", "melee", "archgun", "mod", "arcane", "perk", "enemy")

    def __init__(self, database: Mapping) -> None:
        self.database: dict = dict(database)
        validate_database(self.database)
        upgrades = self.database["upgrades"]
        perk_definitions = {name: Perk.from_record(record) for name, record in upgrades["perks"].items()}
        weapons = self.database["weapons"]
        self.primary = Repository[Primary](weapons["primaries"], lambda record: Primary.from_record(record, perk_definitions))
        self.secondary = Repository[Secondary](weapons["secondaries"], lambda record: Secondary.from_record(record, perk_definitions))
        self.melee = Repository[Melee](weapons["melees"], lambda record: Melee.from_record(record, perk_definitions))
        self.archgun = Repository[Archgun](weapons["archguns"], lambda record: Archgun.from_record(record, perk_definitions))
        self.mod = Repository[Mod](upgrades["mods"], Mod.from_record)
        self.arcane = Repository[Arcane](upgrades["arcanes"], Arcane.from_record)
        self.perk = Repository[Perk](upgrades["perks"], Perk.from_record)
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
    def primary(self) -> Repository[Primary]:
        return self._get().primary

    @property
    def secondary(self) -> Repository[Secondary]:
        return self._get().secondary

    @property
    def melee(self) -> Repository[Melee]:
        return self._get().melee

    @property
    def archgun(self) -> Repository[Archgun]:
        return self._get().archgun

    @property
    def mod(self) -> Repository[Mod]:
        return self._get().mod

    @property
    def arcane(self) -> Repository[Arcane]:
        return self._get().arcane

    @property
    def perk(self) -> Repository[Perk]:
        return self._get().perk

    @property
    def enemy(self) -> Repository[Enemy]:
        return self._get().enemy


arsenal = _LazyArsenal()
