import warnings
from ..domain.perks import Perk, ResolvedPerk
from ..domain.warnings import PerkCompatibilityWarning
from ..domain.weapons import Weapon
from .validation import warn_implementation


def resolve_perks(weapon: Weapon, perks: list[Perk]) -> tuple[ResolvedPerk, ...]:
    for index, perk in enumerate(perks):
        if perk not in weapon.perks:
            raise ValueError(f"{perk.name} is not compatible with {weapon.name}")
        values = weapon.perks[perk]
        expected_tier = index + 1
        if values.tier != expected_tier:
            warnings.warn(f"{perk.name} belongs to {weapon.name} evolution tier {values.tier} but was selected at position {expected_tier}.", PerkCompatibilityWarning, stacklevel=4)
    selected = list(weapon.default_perks)
    for perk in perks:
        if perk not in selected:
            selected.append(perk)
    tiers: dict[int, Perk] = {}
    resolved: list[ResolvedPerk] = []
    for perk in selected:
        if perk not in weapon.perks:
            raise ValueError(f"{perk.name} is not compatible with {weapon.name}")
        warn_implementation(perk.name, perk.implementation_status, stacklevel=5)
        values = weapon.perks[perk]
        if values.tier in tiers and tiers[values.tier] != perk:
            warnings.warn(f"multiple evolution perks selected for tier {values.tier}; keeping {tiers[values.tier].name}.", PerkCompatibilityWarning, stacklevel=4)
            continue
        tiers[values.tier] = perk
        resolved.append(weapon.resolve_perk(perk))
    return tuple(resolved)
