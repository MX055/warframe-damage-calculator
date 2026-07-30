from __future__ import annotations

import warnings
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping, Protocol, Self

from .damage import Dist
from .enemies import Enemy
from .results import AttackResult
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
    max_range: float | None = None
    damage_bonus: float = 0
    initial_combo: float = 0
    heavy_attack_efficiency: float = 0
    zoom: float = 0
    accuracy: float = 0
    recoil: float = 0
    noise_level: str = "alarming"
    falloff: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.punch_through = float(self.punch_through)
        if self.punch_through < 0: raise ValueError("punch_through must be nonnegative")
        if self.range < 0: raise ValueError("range must be nonnegative")
        if self.max_range is not None and self.max_range < 0: raise ValueError("max_range must be nonnegative")
        if not self.falloff: return
        start_range = float(self.falloff.get("start_range", 0))
        end_range = float(self.falloff.get("end_range", 0))
        final_value = self.falloff.get("final_multiplier")
        final_multiplier = 1.0 if final_value is None else float(final_value)
        maximum = end_range if self.max_range is None else self.max_range
        if not 0 <= start_range <= end_range <= maximum: raise ValueError("falloff ranges must satisfy 0 <= start_range <= end_range <= max_range")
        if not 0 <= final_multiplier <= 1: raise ValueError("falloff final_multiplier must be between 0 and 1")

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


class UnimplementedUpgradeWarning(UserWarning):
    pass


class ResultsService(Protocol):
    main: AttackResult

    def resolve(self) -> None: ...


class FormatterService(Protocol):
    def summary(self) -> str: ...
    def upgrades(self) -> str: ...


class ResultsFactory(Protocol):
    def __call__(self, weapon: Weapon, *, resolve: bool = True) -> ResultsService: ...


class FormatterFactory(Protocol):
    def __call__(self, weapon: Weapon) -> FormatterService: ...


_results_factory: ResultsFactory | None = None
_formatter_factory: FormatterFactory | None = None


def configure_weapon_services(results_factory: ResultsFactory, formatter_factory: FormatterFactory) -> None:
    global _results_factory, _formatter_factory
    _results_factory = results_factory
    _formatter_factory = formatter_factory


class Weapon:
    default_type: ClassVar[str] = "weapon"

    def __init__(self, *, name: str, type: str | None = None, subtype: str | None = None, attacks: list[Attack], disposition: float = 0, reload_time: float = 0, magazine_size: float = 1, recharge_delay: float | None = None, recharge_rate: float | None = None, incarnon_charges: float | None = None, incarnon_recharge_count: float | None = None, evolutions: Mapping[str, Any] | None = None, traits: set[str] | None = None, combo: Mapping[str, Any] | None = None, runtime: Mapping[str, Any] | None = None, _resolve: bool = True) -> None:
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
                        if "when" not in effect: continue
                        condition = str(effect["when"])
                        maximum = effect.get("stacks")
                        value = int(maximum) if maximum not in (None, "inf") else True
                        if isinstance(value, int) and not isinstance(value, bool): condition_defaults[condition] = max(int(condition_defaults.get(condition, 0)), value)
                        else: condition_defaults.setdefault(condition, value)
        conditions = set(condition_defaults)
        defaults = {"attack": attacks[0].name, "evolutions": {}, "combo": self.combo.get("max_combo", 12), "stance_combo": "neutral", "ability_strength": 1.0} | condition_defaults
        defaults.update(runtime or {})
        self.runtime = Runtime({"attack", "evolutions", "combo", "stance_combo", "ability_strength", *conditions}, defaults)
        self.build = Build()
        self.target: Enemy | None = Enemy()
        if _results_factory is None or _formatter_factory is None: raise RuntimeError("weapon services are not configured")
        self.results = _results_factory(self, resolve=_resolve)
        self.format = _formatter_factory(self)

    def set(self, *, attack: str | None = None, evolutions: Mapping[int | str, int | str] | None = None, **values: Any) -> Self:
        if attack is not None:
            if attack not in self.attacks: raise ValueError(f"unknown attack {attack!r}")
            values["attack"] = attack
        if evolutions is not None: values["evolutions"] = dict(evolutions)
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
            if not upgrade.implemented: warnings.warn(f"{upgrade.name} is not implemented and will not affect calculated results.", UnimplementedUpgradeWarning, stacklevel=3)
            compatibility = upgrade.compatibility
            matches_type = not compatibility.types or self.type.casefold() in {value.casefold() for value in compatibility.types}
            matches_subtype = not compatibility.subtypes or self.subtype is not None and self.subtype.casefold() in {value.casefold() for value in compatibility.subtypes}
            matches_name = not compatibility.names or self.name.casefold() in {value.casefold() for value in compatibility.names}
            if not (matches_type and matches_subtype and matches_name): warnings.warn(f"{upgrade.name} is not compatible with {self.name}", BuildCompatibilityWarning, stacklevel=3)
            attacks = tuple(self.attacks.values())
            if compatibility.categories and not any(attack.category in compatibility.categories for attack in attacks): warnings.warn(f"{upgrade.name} has no compatible attack category on {self.name}", BuildCompatibilityWarning, stacklevel=3)
            if compatibility.triggers and not any(attack.trigger in compatibility.triggers for attack in attacks): warnings.warn(f"{upgrade.name} has no compatible trigger on {self.name}", BuildCompatibilityWarning, stacklevel=3)
            if compatibility.aoe is not None and not any(attack.aoe is compatibility.aoe for attack in attacks): warnings.warn(f"{upgrade.name} has no compatible area type on {self.name}", BuildCompatibilityWarning, stacklevel=3)
            conflicts = {other.name for other in previous if other.name in upgrade.conflicts or upgrade.name in other.conflicts}
            if conflicts: warnings.warn(f"{upgrade.name} conflicts with {', '.join(sorted(conflicts))}", BuildCompatibilityWarning, stacklevel=3)
            previous.append(upgrade)

    def copy(self, *, resolve: bool = True) -> Self:
        copied = type(self)(name=self.name, type=self.type, subtype=self.subtype, attacks=deepcopy(list(self.attacks.values())), disposition=self.disposition, reload_time=self.reload_time, magazine_size=self.magazine_size, recharge_delay=self.recharge_delay, recharge_rate=self.recharge_rate, incarnon_charges=self.incarnon_charges, incarnon_recharge_count=self.incarnon_recharge_count, evolutions=self.evolutions, traits=self.traits, combo=self.combo, runtime=self.runtime.as_dict(), _resolve=False)
        copied.build = self.build.copy()
        copied.target = self.target.copy() if self.target is not None else None
        if resolve: copied.results.resolve()
        return copied


class Primary(Weapon):
    default_type = "primary"


class Secondary(Weapon):
    default_type = "secondary"


class Melee(Weapon):
    default_type = "melee"
