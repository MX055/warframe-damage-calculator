from __future__ import annotations

from ..domain.loadouts import Loadout
from ..domain.perks import Perk
from ..domain.upgrades import Upgrade
from ..domain.weapons import Weapon


def format_weapon(weapon: Weapon) -> str:
    attacks = ", ".join(weapon.attacks)
    perks = ", ".join(sorted((perk.name for perk in weapon.perks), key=str.casefold)) or "None"
    return f"{weapon.name}\nType: {weapon.type}\nSubtype: {weapon.subtype or '-'}\nAttacks: {attacks}\nPerks: {perks}"


def format_upgrade(upgrade: Upgrade) -> str:
    stats = ", ".join(upgrade.stats) or "None"
    return f"{upgrade.name}\nType: {upgrade.type}\nSlot: {upgrade.slot}\nStats: {stats}"


def format_perk(perk: Perk) -> str:
    stats = ", ".join(perk.stats) or "None"
    return f"{perk.name}\nStats: {stats}"


def format_loadout(loadout: Loadout) -> str:
    mods = "\n".join(f"- {mod.name}" for mod in loadout.mods) or "- None"
    arcanes = "\n".join(f"- {arcane.name}" for arcane in loadout.arcanes) or "- None"
    perks = "\n".join(f"- {perk.name}" for perk in loadout.evolutions) or "- None"
    return f"Mods:\n{mods}\n\nArcanes:\n{arcanes}\n\nPerks:\n{perks}"
