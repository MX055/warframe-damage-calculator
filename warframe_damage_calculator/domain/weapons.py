from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any, ClassVar, Self

from .attacks import Attack, AttackStats, Falloff, Inheritance, Links, RelatedAttacks, resolve_child_keys
from .implementation import ImplementationStatus
from .perks import Perk, PerkValues, ResolvedPerk, resolve_perk

__all__ = ("Attack", "AttackStats", "Falloff", "Inheritance", "Links", "RelatedAttacks", "Archgun", "Melee", "Primary", "Secondary", "Weapon")

def _restore_weapon(cls: type[Weapon], values: dict[str, Any]) -> Weapon:
    return cls(**values)



class Weapon:
    type: ClassVar[str] = "weapon"

    def __init__(self, *, name: str, description: str = "", subtype: str | None = None, attacks: list[Attack] | Mapping[str, Attack], disposition: float = 0, reload_time: float = 0, magazine_size: float = 1, recharge_delay: float | None = None, recharge_rate: float | None = None, incarnon_charges: float | None = None, incarnon_recharge_count: float | None = None, perks: list[PerkValues] | None = None, traits: set[str] | None = None, combo: Mapping[str, Any] | None = None, calculation_defaults: Mapping[str, Any] | None = None, implementation_status: ImplementationStatus | None = None) -> None:
        if not attacks: raise ValueError("weapon requires at least one attack")
        self.name = name
        self.description = description
        self.implementation_status = implementation_status or ImplementationStatus()
        self.subtype = subtype
        loaded = dict(attacks) if isinstance(attacks, Mapping) else {attack.name.replace(" ", "_").casefold(): attack for attack in attacks}
        for attack in loaded.values():
            attack.links.children = resolve_child_keys(attack.links.children, loaded)
        self.attacks = loaded
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
        defaults = {"stance_combo": "neutral", "ability_strength": 1.0}
        defaults.update(calculation_defaults or {})
        self.calculation_defaults = MappingProxyType(defaults)

    @property
    def default_attack(self) -> str:
        return next(iter(self.attacks))

    @property
    def default_perks(self) -> tuple[Perk, ...]:
        tier = self.perk_choices.get(1, {})
        return tuple(tier.values()) if len(tier) == 1 else ()

    def resolve_perk(self, perk: Perk) -> ResolvedPerk:
        try: values = self.perks[perk]
        except KeyError: raise ValueError(f"{perk.name} is not available for {self.name}") from None
        return resolve_perk(values, weapon_name=self.name, perk=perk)

    @classmethod
    def from_record(cls, record: Mapping[str, Any], perks: Mapping[str, Perk] | None = None) -> Weapon:
        allowed = {"name", "description", "subtype", "attacks", "disposition", "reload_time", "magazine_size", "recharge_delay", "recharge_rate", "incarnon_charges", "incarnon_recharge_count", "evolutions", "exalted", "pseudo_exalted", "progenitor", "companion", "combo", "implementation_status"}
        unknown = set(record) - allowed
        if unknown: raise TypeError(f"unknown weapon fields: {', '.join(sorted(unknown))}")
        attacks = {name: Attack.from_record(attack) for name, attack in record["attacks"].items()}
        traits = {name for name in ("exalted", "pseudo_exalted", "progenitor", "companion") if record.get(name)}
        perk_index = perks or {}
        perk_values = [PerkValues.from_record(perk_index[str(choice["perk"])], int(tier), int(choice_number), choice) for tier, choices in record.get("evolutions", {}).items() for choice_number, choice in choices.items()]
        return cls(name=str(record["name"]), description=str(record.get("description", "")), subtype=record.get("subtype"), attacks=attacks, disposition=float(record.get("disposition", 0)), reload_time=float(record.get("reload_time", 0)), magazine_size=float(record.get("magazine_size", 1)), recharge_delay=record.get("recharge_delay"), recharge_rate=record.get("recharge_rate"), incarnon_charges=record.get("incarnon_charges"), incarnon_recharge_count=record.get("incarnon_recharge_count"), perks=perk_values, traits=traits, combo=record.get("combo"), implementation_status=ImplementationStatus.from_record(record.get("implementation_status")))

    def copy(self) -> Self:
        return type(self)(name=self.name, description=self.description, subtype=self.subtype, attacks=deepcopy(self.attacks), disposition=self.disposition, reload_time=self.reload_time, magazine_size=self.magazine_size, recharge_delay=self.recharge_delay, recharge_rate=self.recharge_rate, incarnon_charges=self.incarnon_charges, incarnon_recharge_count=self.incarnon_recharge_count, perks=list(self.perks.values()), traits=self.traits, combo=self.combo, calculation_defaults=self.calculation_defaults, implementation_status=self.implementation_status)

    def __reduce__(self):
        values = {"name": self.name, "description": self.description, "subtype": self.subtype, "attacks": self.attacks, "disposition": self.disposition, "reload_time": self.reload_time, "magazine_size": self.magazine_size, "recharge_delay": self.recharge_delay, "recharge_rate": self.recharge_rate, "incarnon_charges": self.incarnon_charges, "incarnon_recharge_count": self.incarnon_recharge_count, "perks": list(self.perks.values()), "traits": self.traits, "combo": self.combo, "calculation_defaults": dict(self.calculation_defaults), "implementation_status": self.implementation_status}
        return _restore_weapon, (type(self), values)


class Primary(Weapon):
    type = "primary"


class Secondary(Weapon):
    type = "secondary"


class Melee(Weapon):
    type = "melee"


class Archgun(Primary):
    type = "archgun"
