from __future__ import annotations

from ..domain.loadouts import Loadout
from ..domain.perks import Perk, PerkValues
from ..domain.upgrades import Upgrade
from ..domain.weapons import Weapon
from ..domain.effects import resolve_source


def format_weapon(weapon: Weapon) -> str:
    attacks = ", ".join(weapon.attacks)
    perks = ", ".join(sorted((perk.name for perk in weapon.perks), key=str.casefold)) or "None"
    lines = [weapon.name, f"Type: {weapon.type}", f"Subtype: {weapon.subtype or '-'}", f"Attacks: {attacks}", f"Perks: {perks}"]
    if weapon.description: lines.insert(1, f"Description: {weapon.description}")
    return "\n".join(lines)


def format_upgrade(upgrade: Upgrade) -> str:
    stats = ", ".join(upgrade.stats) or "None"
    lines = [upgrade.name, f"Type: {upgrade.type}", f"Slot: {getattr(upgrade, 'slot', '-')}", f"Stats: {stats}"]
    if upgrade.description: lines.insert(1, f"Description: {upgrade.description}")
    return "\n".join(lines)


def format_perk(perk: Perk, values: PerkValues | None = None) -> str:
    stats = ", ".join(perk.stats) or "None"
    lines = [perk.name, f"Stats: {stats}"]
    if values is not None:
        description = str(resolve_source(perk.description_source, {"description": values.description}))
        if description: lines.insert(1, f"Description: {description}")
    return "\n".join(lines)


def format_loadout(loadout: Loadout) -> str:
    mods = "\n".join(f"- {mod.name}" for mod in loadout.mods) or "- None"
    arcanes = "\n".join(f"- {arcane.name}" for arcane in loadout.arcanes) or "- None"
    perks = "\n".join(f"- {perk.name}" for perk in loadout.evolutions) or "- None"
    return f"Mods:\n{mods}\n\nArcanes:\n{arcanes}\n\nPerks:\n{perks}"
