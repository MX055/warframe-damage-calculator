from __future__ import annotations

from typing import Any

from .domain.effects import Effect


def _effects(stats: Any, path: str) -> None:
    if not isinstance(stats, dict): raise ValueError(f"{path}: expected an object")
    for stat, effects in stats.items():
        if not isinstance(effects, list) or not effects: raise ValueError(f"{path}.{stat}: expected effects")
        for index, effect in enumerate(effects):
            location = f"{path}.{stat}[{index}]"
            if set(effect) != {"properties", "manual", "automatic"}: raise ValueError(f"{location}: invalid effect channels")
            try: Effect.from_record(effect)
            except (TypeError, ValueError) as error: raise ValueError(f"{location}: {error}") from error
            if isinstance(effect["properties"].get("value"), (dict, list)): raise ValueError(f"{location}: value must be scalar")


def validate_database(database: dict[str, Any]) -> None:
    allowed_root = {"schema_version", "weapons", "upgrades", "enemies", "riven_stats"}
    if set(database) != allowed_root: raise ValueError(f"database: invalid fields {sorted(set(database) - allowed_root)}")
    if database.get("schema_version") != 6: raise ValueError("schema version 6 is required")
    for section in ("weapons", "upgrades", "enemies", "riven_stats"):
        if not isinstance(database.get(section), dict): raise ValueError(f"{section}: expected an object")
    for name, weapon in database["weapons"].items():
        allowed_weapon = {"name", "type", "subtype", "attacks", "disposition", "reload_time", "magazine_size", "recharge_delay", "recharge_rate", "incarnon_charges", "incarnon_recharge_count", "evolutions", "exalted", "pseudo_exalted", "progenitor", "companion", "combo"}
        if set(weapon) - allowed_weapon: raise ValueError(f"weapons.{name}: invalid fields {sorted(set(weapon) - allowed_weapon)}")
        if weapon.get("name") != name or "ammo" in weapon: raise ValueError(f"weapons.{name}: invalid record")
        if not weapon.get("attacks"): raise ValueError(f"weapons.{name}: attacks are required")
        for attack_name, attack in weapon["attacks"].items():
            if set(attack) - {"trigger", "delivery", "form", "category", "aoe", "children", "stats"}: raise ValueError(f"weapons.{name}.attacks.{attack_name}: invalid fields")
        for tier, perks in weapon.get("evolutions", {}).items():
            for perk, record in perks.items(): _effects(record.get("stats", {}), f"weapons.{name}.evolutions.{tier}.{perk}")
    for name, upgrade in database["upgrades"].items():
        if set(upgrade) - {"name", "kind", "slot", "max_rank", "compatibility", "conflicts", "stats", "combos"}: raise ValueError(f"upgrades.{name}: invalid fields {sorted(set(upgrade) - {'name', 'kind', 'slot', 'max_rank', 'compatibility', 'conflicts', 'stats', 'combos'})}")
        if upgrade.get("name") != name: raise ValueError(f"upgrades.{name}: invalid name")
        if upgrade.get("kind") not in {"mod", "arcane", "buff"}: raise ValueError(f"upgrades.{name}: invalid kind")
        if upgrade.get("slot") not in {"normal", "exilus", "stance", "arcane"}: raise ValueError(f"upgrades.{name}: invalid slot")
        if set(upgrade.get("compatibility", {})) - {"types", "subtypes", "names", "categories", "triggers", "aoe"}: raise ValueError(f"upgrades.{name}.compatibility: invalid fields")
        _effects(upgrade.get("stats", {}), f"upgrades.{name}.stats")
