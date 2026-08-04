from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from importlib.resources import files
from pathlib import Path
from typing import Generic, Self, TypeVar

from ..domain.enemies import Enemy
from ..domain.perks import Perk
from ..domain.upgrades import Arcane, Mod, Upgrade
from ..domain.weapons import Archgun, Attack, Melee, Primary, Secondary, Weapon
from .bundled_names import ArcaneName, ArchgunName, EnemyName, MeleeName, ModName, PerkName, PrimaryName, SecondaryName
from .compatibility import is_upgrade_compatible
from .schema import validate_database


T = TypeVar("T", Weapon, Upgrade, Enemy)
U = TypeVar("U", Mod, Arcane)
N = TypeVar("N", bound=str, default=str)


def _key(value: str) -> str:
    return " ".join(value.split()).casefold()


class Repository(Generic[T, N]):
    __slots__ = ("_records", "_factory", "_index")

    def __init__(self, records: Mapping[str, Mapping], factory: Callable[[Mapping], T]) -> None:
        self._records = dict(records)
        self._factory = factory
        self._index = {_key(name): name for name in records}

    def get(self, name: N) -> T:
        try: record = self._records[self._index[_key(name)]]
        except KeyError: raise KeyError(name) from None
        return self._factory(record)

    def __iter__(self) -> Iterator[str]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)

    @property
    def names(self) -> tuple[N, ...]:
        return tuple(sorted(self._records, key=str.casefold))  # type: ignore[return-value]


class UpgradeRepository(Repository[U, N], Generic[U, N]):
    def is_compatible(self, upgrade: N | U, *, weapon: Weapon, attack: str | Attack | None = None, slot: str | None = None, implemented: bool | None = None, selected: tuple[Upgrade, ...] = ()) -> bool:
        item = self.get(upgrade) if isinstance(upgrade, str) else upgrade
        return is_upgrade_compatible(item, weapon, attack=attack, slot=slot, implemented=implemented, selected=selected)

    def filter(self, *, weapon: Weapon, attack: str | Attack | None = None, slot: str | None = None, implemented: bool | None = None, selected: tuple[Upgrade, ...] = ()) -> tuple[U, ...]:
        return tuple(item for name in self.names if self.is_compatible(item := self.get(name), weapon=weapon, attack=attack, slot=slot, implemented=implemented, selected=selected))


class Arsenal:
    __slots__ = ("database", "primary", "secondary", "melee", "archgun", "mod", "arcane", "perk", "enemy")

    def __init__(self, database: Mapping) -> None:
        self.database: dict = dict(database)
        validate_database(self.database)
        upgrades = self.database["upgrades"]
        perk_definitions = {name: Perk.from_record(record) for name, record in upgrades["perks"].items()}
        weapons = self.database["weapons"]
        self.primary: Repository[Primary, PrimaryName] = Repository(weapons["primaries"], lambda record: Primary.from_record(record, perk_definitions))
        self.secondary: Repository[Secondary, SecondaryName] = Repository(weapons["secondaries"], lambda record: Secondary.from_record(record, perk_definitions))
        self.melee: Repository[Melee, MeleeName] = Repository(weapons["melees"], lambda record: Melee.from_record(record, perk_definitions))
        self.archgun: Repository[Archgun, ArchgunName] = Repository(weapons["archguns"], lambda record: Archgun.from_record(record, perk_definitions))
        self.mod: UpgradeRepository[Mod, ModName] = UpgradeRepository(upgrades["mods"], Mod.from_record)
        self.arcane: UpgradeRepository[Arcane, ArcaneName] = UpgradeRepository(upgrades["arcanes"], Arcane.from_record)
        self.perk: Repository[Perk, PerkName] = Repository(upgrades["perks"], Perk.from_record)
        self.enemy: Repository[Enemy, EnemyName] = Repository(self.database["enemies"], lambda record: Enemy.from_record(record, loaded=True))

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
    def primary(self) -> Repository[Primary, PrimaryName]:
        return self._get().primary

    @property
    def secondary(self) -> Repository[Secondary, SecondaryName]:
        return self._get().secondary

    @property
    def melee(self) -> Repository[Melee, MeleeName]:
        return self._get().melee

    @property
    def archgun(self) -> Repository[Archgun, ArchgunName]:
        return self._get().archgun

    @property
    def mod(self) -> UpgradeRepository[Mod, ModName]:
        return self._get().mod

    @property
    def arcane(self) -> UpgradeRepository[Arcane, ArcaneName]:
        return self._get().arcane

    @property
    def perk(self) -> Repository[Perk, PerkName]:
        return self._get().perk

    @property
    def enemy(self) -> Repository[Enemy, EnemyName]:
        return self._get().enemy


arsenal = _LazyArsenal()
