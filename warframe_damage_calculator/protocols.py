from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from .fields.attack_result import AttackResult
from .fields.upgrade import ResolvedStat, UpgradeData
from .fields.weapon_data import WeaponData
from .fields.weapon_input import WeaponStats


@runtime_checkable
class UpgradeOwner(Protocol):
    data: UpgradeData


@runtime_checkable
class UpgradeResultsView(Protocol):
    static: ResolvedStat
    conditional: ResolvedStat
    modular: ResolvedStat
    stacking: ResolvedStat
    rank_locked: ResolvedStat
    total: ResolvedStat

    def resolve(self, weapon: object | None = None, build: object | None = None) -> None: ...


@runtime_checkable
class BuildUpgradeOwner(Protocol):
    data: UpgradeData
    results: UpgradeResultsView


@runtime_checkable
class BuildOwner(Protocol):
    upgrades: Sequence[BuildUpgradeOwner]


@runtime_checkable
class WeaponCalculatorOwner(Protocol):
    data: WeaponData
    build: BuildOwner
    _attack: str
    _evolutions: Mapping[int, int]
    stats_type: type[WeaponStats]


@runtime_checkable
class ConfigurableWeaponOwner(WeaponCalculatorOwner, Protocol):
    def configure(self, build: BuildOwner | None = None, attack: str | None = None, evolutions: Mapping[int, int] | None = None) -> ConfigurableWeaponOwner: ...

    def copy(self) -> ConfigurableWeaponOwner: ...


@runtime_checkable
class WeaponResultsView(Protocol):
    main: AttackResult
    child: list[AttackResult]

    def resolve(self) -> None: ...

    def contribution_fractions(self) -> Mapping[str, float]: ...


@runtime_checkable
class WeaponFormatterOwner(Protocol):
    data: WeaponData
    results: WeaponResultsView
