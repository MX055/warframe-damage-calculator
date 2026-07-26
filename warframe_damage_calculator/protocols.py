from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from .fields.attack_result import AttackResult
from .fields.enemy import EnemyData
from .fields.upgrade import ResolvedStat, UpgradeData
from .fields.weapon_data import WeaponData
from .fields.weapon_input import WeaponStats


@runtime_checkable
class UpgradeOwner(Protocol):
    data: UpgradeData


@runtime_checkable
class EnemyOwner(Protocol):
    data: EnemyData


@runtime_checkable
class UpgradeResultsView(Protocol):
    static: ResolvedStat
    conditional: ResolvedStat
    modular: ResolvedStat
    stacking: ResolvedStat
    rank_locked: ResolvedStat
    total: ResolvedStat

    def resolve(self, weapon: object | None = None, build: object | None = None) -> None: ...

    def _normalize_effects(self) -> Sequence[object]: ...


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
    target: EnemyOwner | None
    stats_type: type[WeaponStats]


@runtime_checkable
class ConfigurableWeaponOwner(WeaponCalculatorOwner, Protocol):
    def configure(self, build: BuildOwner | BuildUpgradeOwner | None = None, target: EnemyOwner | None | object = ...) -> ConfigurableWeaponOwner: ...

    def set(self, context: Mapping[str, Any] | None = None) -> ConfigurableWeaponOwner: ...

    def copy(self) -> ConfigurableWeaponOwner: ...


@runtime_checkable
class WeaponResultsView(Protocol):
    main: AttackResult
    child: list[AttackResult]

    def resolve(self) -> None: ...

    def shapley_contributions(self, target: str = "total_dps") -> Mapping[str, float]: ...

    def removal_contributions(self, target: str = "total_dps") -> Mapping[str, float]: ...


@runtime_checkable
class WeaponFormatterOwner(Protocol):
    data: WeaponData
    results: WeaponResultsView
