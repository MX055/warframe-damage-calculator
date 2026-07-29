from __future__ import annotations

import warnings
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping, Self

from .damage import Dist
from .enemies import Enemy
from .results import WeaponResults
from .upgrades import Build, Runtime, Upgrade


@dataclass(slots=True)
class AttackStats:
    ammo_cost: float = 1
    damage: Dist = field(default_factory=Dist)
    forced_procs: Dist = field(default_factory=Dist)
    punch_through: float | str = 0
    crit_chance: float = 0
    crit_damage: float = 1
    status_chance: float = 0
    status_duration: float = 6
    multishot: float = 1
    fire_rate: float = 0.05
    attack_speed: float | None = None
    burst_count: int = 1
    burst_delay: float = 0
    charge_time: float = 0
    co_factor: float = 1
    co_effect: str = "adds"
    range: float = 0
    damage_bonus: float = 0
    initial_combo: float = 0
    heavy_attack_efficiency: float = 0
    zoom: float = 0
    accuracy: float = 0
    recoil: float = 0
    noise_level: str = "alarming"
    falloff: Mapping[str, float] = field(default_factory=dict)

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> AttackStats:
        values = dict(record)
        values["damage"] = Dist(values.get("damage", {}))
        values["forced_procs"] = Dist(values.get("forced_procs", {}))
        return cls(**values)


@dataclass(slots=True)
class Attack:
    name: str
    trigger: str | None = None
    delivery: str | None = None
    form: str = "normal"
    category: str = "normal"
    aoe: bool = False
    children: list[str] = field(default_factory=list)
    stats: AttackStats = field(default_factory=AttackStats)

    @classmethod
    def from_record(cls, name: str, record: Mapping[str, Any]) -> Attack:
        values = dict(record)
        values["name"] = name
        values["stats"] = AttackStats.from_record(values.get("stats", {}))
        return cls(**values)


class BuildCompatibilityWarning(UserWarning):
    pass


class Weapon:
    default_type: ClassVar[str] = "weapon"

    def __init__(self, *, name: str, type: str | None = None, subtype: str | None = None, attacks: list[Attack], disposition: float = 0, reload_time: float = 0, magazine_size: float = 1, recharge_delay: float | None = None, recharge_rate: float | None = None, incarnon_charges: float | None = None, incarnon_recharge_count: float | None = None, evolutions: Mapping[str, Any] | None = None, traits: set[str] | None = None, combo: Mapping[str, Any] | None = None, runtime: Mapping[str, Any] | None = None) -> None:
        if not attacks: raise ValueError("weapon requires at least one attack")
        self.name = name
        self.type = type or self.default_type
        self.subtype = subtype
        self.attacks = {attack.name: attack for attack in attacks}
        self.disposition = float(disposition)
        self.reload_time = float(reload_time)
        self.magazine_size = float(magazine_size)
        self.recharge_delay = recharge_delay
        self.recharge_rate = recharge_rate
        self.incarnon_charges = incarnon_charges
        self.incarnon_recharge_count = incarnon_recharge_count
        self.evolutions = deepcopy(dict(evolutions or {}))
        self.traits = set(traits or ())
        self.combo = deepcopy(dict(combo or {}))
        condition_defaults: dict[str, Any] = {}
        for tiers in self.evolutions.values():
            for perk in tiers.values():
                for effects in perk.get("stats", {}).values():
                    for effect in effects:
                        manual = {token.split(":", 1)[0]: token.split(":", 1)[1] for token in effect.get("manual", [])}
                        if "WHEN" not in manual: continue
                        condition = manual["WHEN"].lower()
                        maximum = manual.get("STACKS")
                        value = int(maximum) if maximum not in (None, "INF") else True
                        if isinstance(value, int) and not isinstance(value, bool): condition_defaults[condition] = max(int(condition_defaults.get(condition, 0)), value)
                        else: condition_defaults.setdefault(condition, value)
        conditions = set(condition_defaults)
        defaults = {"attack": attacks[0].name, "evolutions": {}, "combo": self.combo.get("max_combo", 12), "stance_combo": "neutral", "ability_strength": 1.0} | condition_defaults
        defaults.update(runtime or {})
        self.runtime = Runtime({"attack", "evolutions", "combo", "stance_combo", "ability_strength", *conditions}, defaults)
        self.build = Build()
        self.target: Enemy | None = Enemy()
        self.results = WeaponResults(self)
        from ..formatting import WeaponFormatter
        self.format = WeaponFormatter(self)

    def set(self, **values: Any) -> Self:
        if "attack" in values and values["attack"] not in self.attacks: raise ValueError(f"unknown attack {values['attack']!r}")
        self.runtime.set(**values)
        self.results.resolve()
        return self

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Weapon:
        allowed = {"name", "type", "subtype", "attacks", "disposition", "reload_time", "magazine_size", "recharge_delay", "recharge_rate", "incarnon_charges", "incarnon_recharge_count", "evolutions", "exalted", "pseudo_exalted", "progenitor", "companion", "combo"}
        unknown = set(record) - allowed
        if unknown: raise TypeError(f"unknown weapon fields: {', '.join(sorted(unknown))}")
        attacks = [Attack.from_record(name, attack) for name, attack in record["attacks"].items()]
        traits = {name for name in ("exalted", "pseudo_exalted", "progenitor", "companion") if record.get(name)}
        return cls(name=str(record["name"]), type=str(record["type"]), subtype=record.get("subtype"), attacks=attacks, disposition=float(record.get("disposition", 0)), reload_time=float(record.get("reload_time", 0)), magazine_size=float(record.get("magazine_size", 1)), recharge_delay=record.get("recharge_delay"), recharge_rate=record.get("recharge_rate"), incarnon_charges=record.get("incarnon_charges"), incarnon_recharge_count=record.get("incarnon_recharge_count"), evolutions=record.get("evolutions"), traits=traits, combo=record.get("combo"))

    def configure(self, build: Build | Upgrade | None = None, target: Enemy | None = None) -> Self:
        if build is not None: self.build = build.copy() if isinstance(build, Build) else Build(build)
        if target is not None: self.target = target.copy()
        self._warn_build()
        self.results.resolve()
        return self

    def _warn_build(self) -> None:
        previous: list[Upgrade] = []
        for upgrade in self.build:
            compatibility = upgrade.compatibility
            identity = {str(value).casefold() for value in compatibility.types + compatibility.subtypes + compatibility.names}
            actual = {str(value).casefold() for value in (self.type, self.subtype, self.name) if value is not None}
            if identity and not identity & actual: warnings.warn(f"{upgrade.name} is not compatible with {self.name}", BuildCompatibilityWarning, stacklevel=3)
            attacks = tuple(self.attacks.values())
            if compatibility.categories and not any(attack.category in compatibility.categories for attack in attacks): warnings.warn(f"{upgrade.name} has no compatible attack category on {self.name}", BuildCompatibilityWarning, stacklevel=3)
            if compatibility.triggers and not any(attack.trigger in compatibility.triggers for attack in attacks): warnings.warn(f"{upgrade.name} has no compatible trigger on {self.name}", BuildCompatibilityWarning, stacklevel=3)
            if compatibility.aoe is not None and not any(attack.aoe is compatibility.aoe for attack in attacks): warnings.warn(f"{upgrade.name} has no compatible area type on {self.name}", BuildCompatibilityWarning, stacklevel=3)
            conflicts = {other.name for other in previous if other.name in upgrade.conflicts or upgrade.name in other.conflicts}
            if conflicts: warnings.warn(f"{upgrade.name} conflicts with {', '.join(sorted(conflicts))}", BuildCompatibilityWarning, stacklevel=3)
            previous.append(upgrade)

    def copy(self) -> Self:
        copied = type(self)(name=self.name, type=self.type, subtype=self.subtype, attacks=deepcopy(list(self.attacks.values())), disposition=self.disposition, reload_time=self.reload_time, magazine_size=self.magazine_size, recharge_delay=self.recharge_delay, recharge_rate=self.recharge_rate, incarnon_charges=self.incarnon_charges, incarnon_recharge_count=self.incarnon_recharge_count, evolutions=self.evolutions, traits=self.traits, combo=self.combo, runtime=self.runtime.as_dict())
        copied.build = self.build.copy()
        copied.target = self.target.copy() if self.target is not None else None
        copied.results.resolve()
        return copied


class Primary(Weapon):
    default_type = "primary"


class Secondary(Weapon):
    default_type = "secondary"


class Melee(Weapon):
    default_type = "melee"
