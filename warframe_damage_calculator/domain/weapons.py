from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, Self

from .damage import Dist
from .implementation import ImplementationStatus
from .perks import Perk, PerkValues, ResolvedPerk, resolve_perk


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
    generated_by: str | None = None
    stats: AttackStats = field(default_factory=AttackStats)

    @classmethod
    def from_record(cls, name: str, record: Mapping[str, Any]) -> Attack:
        values = dict(record)
        record_name = str(values.pop("name", name))
        if record_name != name: raise ValueError(f"attack key {name!r} does not match record name {record_name!r}")
        values["name"] = record_name
        values["stats"] = AttackStats.from_record(values.get("stats", {}))
        return cls(**values)


class Weapon:
    type: ClassVar[str] = "weapon"

    def __init__(self, *, name: str, subtype: str | None = None, attacks: list[Attack], disposition: float = 0, reload_time: float = 0, magazine_size: float = 1, recharge_delay: float | None = None, recharge_rate: float | None = None, incarnon_charges: float | None = None, incarnon_recharge_count: float | None = None, perks: list[PerkValues] | None = None, traits: set[str] | None = None, combo: Mapping[str, Any] | None = None, calculation_defaults: Mapping[str, Any] | None = None, implementation_status: ImplementationStatus | None = None) -> None:
        if not attacks: raise ValueError("weapon requires at least one attack")
        self.name = name
        self.implementation_status = implementation_status or ImplementationStatus()
        self.subtype = subtype
        self.attacks = {attack.name: attack for attack in attacks}
        self.disposition = float(disposition)
        self.reload_time = float(reload_time)
        self.magazine_size = float(magazine_size)
        self.recharge_delay = recharge_delay
        self.recharge_rate = recharge_rate
        self.incarnon_charges = incarnon_charges
        self.incarnon_recharge_count = incarnon_recharge_count
        perk_values = list(perks or ())
        if len({values.perk for values in perk_values}) != len(perk_values): raise ValueError(f"{name} contains duplicate perk definitions")
        self.perks = MappingProxyType({values.perk: values for values in perk_values})
        choices: dict[int, dict[int, Perk]] = {}
        for values in perk_values: choices.setdefault(values.tier, {})[values.choice] = values.perk
        self.perk_choices = MappingProxyType({tier: MappingProxyType(dict(sorted(tier_choices.items()))) for tier, tier_choices in sorted(choices.items())})
        self.traits = set(traits or ())
        self.combo = deepcopy(dict(combo or {}))
        condition_defaults: dict[str, Any] = {}
        for perk in self.perks:
            for effects in perk.stats.values():
                for effect in effects:
                    if effect.when is None: continue
                    condition = effect.when
                    maximum = effect.stacks
                    value = int(maximum) if maximum not in (None, "inf") else True
                    if isinstance(value, int) and not isinstance(value, bool): condition_defaults[condition] = max(int(condition_defaults.get(condition, 0)), value)
                    else: condition_defaults.setdefault(condition, value)
        defaults = {"combo": self.combo.get("max_combo", 12), "stance_combo": "neutral", "ability_strength": 1.0} | condition_defaults
        defaults.update(calculation_defaults or {})
        self.calculation_defaults = MappingProxyType(defaults)

    @property
    def default_attack(self) -> str:
        return next(iter(self.attacks))

    @property
    def default_perks(self) -> tuple[Perk, ...]:
        tier = self.perk_choices.get(1, {})
        return tuple(tier.values()) if len(tier) == 1 else ()

    def resolve_perk(self, perk: Perk, *, state: Mapping[str, object] | None = None) -> ResolvedPerk:
        try: values = self.perks[perk]
        except KeyError: raise ValueError(f"{perk.name} is not available for {self.name}") from None
        return resolve_perk(values, weapon_name=self.name, state=dict(self.calculation_defaults) | dict(state or {}))

    @classmethod
    def from_record(cls, record: Mapping[str, Any], perks: Mapping[str, Perk] | None = None) -> Weapon:
        allowed = {"name", "subtype", "attacks", "disposition", "reload_time", "magazine_size", "recharge_delay", "recharge_rate", "incarnon_charges", "incarnon_recharge_count", "evolutions", "exalted", "pseudo_exalted", "progenitor", "companion", "combo", "implementation_status"}
        unknown = set(record) - allowed
        if unknown: raise TypeError(f"unknown weapon fields: {', '.join(sorted(unknown))}")
        attacks = [Attack.from_record(name, attack) for name, attack in record["attacks"].items()]
        traits = {name for name in ("exalted", "pseudo_exalted", "progenitor", "companion") if record.get(name)}
        perk_index = perks or {}
        perk_values = [PerkValues.from_record(perk_index[str(choice["perk"])], int(tier), int(choice_number), choice) for tier, choices in record.get("evolutions", {}).items() for choice_number, choice in choices.items()]
        return cls(name=str(record["name"]), subtype=record.get("subtype"), attacks=attacks, disposition=float(record.get("disposition", 0)), reload_time=float(record.get("reload_time", 0)), magazine_size=float(record.get("magazine_size", 1)), recharge_delay=record.get("recharge_delay"), recharge_rate=record.get("recharge_rate"), incarnon_charges=record.get("incarnon_charges"), incarnon_recharge_count=record.get("incarnon_recharge_count"), perks=perk_values, traits=traits, combo=record.get("combo"), implementation_status=ImplementationStatus.from_record(record.get("implementation_status")))

    def copy(self) -> Self:
        return type(self)(name=self.name, subtype=self.subtype, attacks=deepcopy(list(self.attacks.values())), disposition=self.disposition, reload_time=self.reload_time, magazine_size=self.magazine_size, recharge_delay=self.recharge_delay, recharge_rate=self.recharge_rate, incarnon_charges=self.incarnon_charges, incarnon_recharge_count=self.incarnon_recharge_count, perks=list(self.perks.values()), traits=self.traits, combo=self.combo, calculation_defaults=self.calculation_defaults, implementation_status=self.implementation_status)


class Primary(Weapon):
    type = "primary"


class Secondary(Weapon):
    type = "secondary"


class Melee(Weapon):
    type = "melee"


class Archgun(Primary):
    type = "archgun"
