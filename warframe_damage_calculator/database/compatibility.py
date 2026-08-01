from __future__ import annotations

from collections.abc import Iterable

from ..domain.upgrades import Arcane, Mod, Upgrade
from ..domain.weapons import Attack, Weapon


def _selected_attacks(weapon: Weapon, attack: str | Attack | None) -> tuple[Attack, ...]:
    if attack is None: return tuple(weapon.attacks.values())
    if isinstance(attack, Attack): return (attack,)
    try: return (weapon.attacks[attack],)
    except KeyError: raise ValueError(f"unknown attack {attack!r} for {weapon.name}") from None


def _arcane_compatible(arcane: Arcane, weapon: Weapon) -> bool:
    name = arcane.name
    if weapon.type == "primary":
        if name == "Shotgun Vendetta": return weapon.subtype == "shotgun"
        if name == "Longbow Sharpshot": return weapon.subtype == "bow"
        return name.startswith("Primary ") or name == "Fractalized Reset"
    if weapon.type == "secondary": return name.startswith(("Secondary ", "Cascadia ")) or name in {"Akimbo Slip Shot", "Conjunction Voltage"}
    if weapon.type == "melee": return name.startswith("Melee ")
    return True


def is_upgrade_compatible(upgrade: Mod | Arcane, weapon: Weapon, *, attack: str | Attack | None = None, slot: str | None = None, implemented: bool | None = None, selected: Iterable[Upgrade] = ()) -> bool:
    if implemented is not None and upgrade.implemented is not implemented: return False
    if slot is not None and upgrade.slot != slot: return False
    compatibility = upgrade.compatibility
    types = {value.casefold() for value in compatibility.types}
    subtypes = {value.casefold() for value in compatibility.subtypes}
    names = {value.casefold() for value in compatibility.names}
    if types and weapon.type.casefold() not in types: return False
    if subtypes and (weapon.subtype is None or weapon.subtype.casefold() not in subtypes): return False
    if names and weapon.name.casefold() not in names: return False
    attacks = _selected_attacks(weapon, attack)
    if not any(
        (not compatibility.categories or candidate.category in compatibility.categories)
        and (not compatibility.triggers or candidate.trigger in compatibility.triggers)
        and (compatibility.aoe is None or candidate.aoe is compatibility.aoe)
        for candidate in attacks
    ): return False
    if isinstance(upgrade, Arcane) and not _arcane_compatible(upgrade, weapon): return False
    if isinstance(upgrade, Mod) and upgrade.slot == "exilus_mod" and "range" in upgrade.stats and not any(candidate.delivery == "beam" for candidate in attacks): return False
    for other in selected:
        if other.name in upgrade.conflicts or upgrade.name in getattr(other, "conflicts", ()): return False
    return True
