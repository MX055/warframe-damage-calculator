import warnings
from collections.abc import Mapping

from ..domain.perks import Perk, ResolvedPerk
from ..domain.warnings import PerkCompatibilityWarning
from ..domain.weapons import Weapon
from .validation import warn_implementation


def resolve_perks(weapon: Weapon, perks: list[Perk], state: Mapping[str, object]) -> tuple[ResolvedPerk, ...]:
    selected = list(weapon.default_perks)
    selected.extend(perk for perk in perks if perk not in selected)
    tiers: dict[int, Perk] = {}
    resolved: list[ResolvedPerk] = []
    for perk in selected:
        if perk not in weapon.perks:
            warnings.warn(f"{perk.name} is not compatible with {weapon.name} and will be ignored.", PerkCompatibilityWarning, stacklevel=4)
            continue
        warn_implementation(perk.name, perk.implementation_status, stacklevel=5)
        result = weapon.resolve_perk(perk, state=state)
        if result.tier in tiers and tiers[result.tier] != perk: raise ValueError(f"multiple evolution perks selected for tier {result.tier}")
        tiers[result.tier] = perk
        resolved.append(result)
    return tuple(resolved)
