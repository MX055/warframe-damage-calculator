from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from ..domain.damage import Dist
from ..domain.enemies import Enemy
from ..domain.upgrades import ResolvedEffect


class RuntimeProtocol(Protocol):
    attack: str
    evolutions: Mapping[int | str, int | str]
    combo: float
    stance_combo: str
    ability_strength: float

    def as_dict(self) -> dict[str, Any]: ...


class AttackStatsProtocol(Protocol):
    ammo_cost: float
    damage: Dist
    forced_procs: Dist
    punch_through: float
    crit_chance: float
    crit_damage: float
    status_chance: float
    status_duration: float
    multishot: float
    fire_rate: float
    attack_speed: float | None
    burst_count: int
    burst_delay: float
    charge_time: float
    co_factor: float
    co_effect: str
    range: float
    max_range: float | None
    damage_bonus: float
    initial_combo: float
    heavy_attack_efficiency: float
    zoom: float
    accuracy: float
    recoil: float
    noise_level: str
    falloff: Mapping[str, float]


class AttackProtocol(Protocol):
    name: str
    trigger: str | None
    delivery: str | None
    form: str
    category: str
    aoe: bool
    children: list[str]
    stats: AttackStatsProtocol


class UpgradeProtocol(Protocol):
    name: str
    slot: str
    implemented: bool
    combos: Mapping[str, Any]

    def resolve_manual(self) -> tuple[ResolvedEffect, ...]: ...


class BuildProtocol(Protocol):
    def __iter__(self) -> Iterable[UpgradeProtocol]: ...


class WeaponProtocol(Protocol):
    name: str
    type: str
    subtype: str | None
    attacks: Mapping[str, AttackProtocol]
    reload_time: float
    magazine_size: float
    recharge_delay: float | None
    recharge_rate: float | None
    incarnon_charges: float | None
    incarnon_recharge_count: float | None
    evolutions: Mapping[str, Mapping[str, Mapping[str, Any]]]
    traits: set[str]
    combo: Mapping[str, Any]
    runtime: RuntimeProtocol
    build: BuildProtocol
    target: Enemy | None
