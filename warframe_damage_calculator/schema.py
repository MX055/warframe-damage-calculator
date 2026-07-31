from __future__ import annotations

from math import isfinite
from typing import Any

from .domain.effects import AUTOMATIC_FIELDS, EFFECT_FIELDS, REPEATABLE_AUTOMATIC_FIELDS, Effect


def _validate_automatic(automatic: Any, path: str) -> None:
    if not isinstance(automatic, dict) or not set(automatic) <= AUTOMATIC_FIELDS: raise ValueError(f"{path}: invalid automatic fields")
    for key, value in automatic.items():
        values = value if isinstance(value, list) else [value]
        if isinstance(value, list) and (key not in REPEATABLE_AUTOMATIC_FIELDS or not value): raise ValueError(f"{path}.{key}: invalid repeated values")
        if any(not isinstance(item, (int, float, bool, str)) or isinstance(item, str) and not item for item in values): raise ValueError(f"{path}.{key}: expected scalar values")


def _effects(stats: Any, path: str, *, placeholders: bool = False) -> None:
    if not isinstance(stats, dict): raise ValueError(f"{path}: expected an object")
    for stat, effects in stats.items():
        if not isinstance(effects, list) or not effects: raise ValueError(f"{path}.{stat}: expected effects")
        for index, effect in enumerate(effects):
            location = f"{path}.{stat}[{index}]"
            if not isinstance(effect, dict) or not set(effect) <= EFFECT_FIELDS or "value" not in effect or "automatic" not in effect: raise ValueError(f"{location}: invalid effect fields")
            if placeholders and effect["value"] != "$weapon": raise ValueError(f"{location}: expected '$weapon' placeholder")
            if not placeholders and effect["value"] == "$weapon": raise ValueError(f"{location}: unresolved placeholder")
            try: Effect.from_record(effect)
            except (TypeError, ValueError) as error: raise ValueError(f"{location}: {error}") from error
            if isinstance(effect["value"], (dict, list)): raise ValueError(f"{location}: value must be scalar")
            _validate_automatic(effect["automatic"], f"{location}.automatic")


def _implementation_status(value: Any, path: str) -> None:
    if value is None: return
    if not isinstance(value, dict) or set(value) - {"state", "missing_features", "notes"}: raise ValueError(f"{path}: invalid fields")
    state = value.get("state", "implemented")
    if state not in {"implemented", "partial", "not_implemented", "unknown"}: raise ValueError(f"{path}.state: invalid state")
    features = value.get("missing_features", [])
    if not isinstance(features, list) or any(not isinstance(feature, str) or not feature.strip() for feature in features): raise ValueError(f"{path}.missing_features: expected nonempty strings")
    if state == "implemented" and features: raise ValueError(f"{path}: implemented records cannot have missing features")
    if state in {"partial", "not_implemented"} and not features: raise ValueError(f"{path}: {state} records require missing features")
    if value.get("notes") is not None and not isinstance(value["notes"], str): raise ValueError(f"{path}.notes: expected a string")


def validate_database(database: dict[str, Any]) -> None:
    allowed_root = {"schema_version", "weapons", "upgrades", "perks", "enemies", "riven_stats"}
    missing_root = allowed_root - set(database)
    unexpected_root = set(database) - allowed_root
    if missing_root: raise ValueError(f"database: missing fields {sorted(missing_root)}")
    if unexpected_root: raise ValueError(f"database: unexpected fields {sorted(unexpected_root)}")
    if database.get("schema_version") != 15: raise ValueError("schema version 15 is required")
    for section in ("weapons", "upgrades", "perks", "enemies", "riven_stats"):
        if not isinstance(database.get(section), dict): raise ValueError(f"{section}: expected an object")
    for name, perk in database["perks"].items():
        if not isinstance(perk, dict) or set(perk) - {"name", "description", "stats", "implementation_status"}: raise ValueError(f"perks.{name}: invalid fields")
        if perk.get("name") != name: raise ValueError(f"perks.{name}: invalid name")
        _implementation_status(perk.get("implementation_status"), f"perks.{name}.implementation_status")
        _effects(perk.get("stats", {}), f"perks.{name}.stats", placeholders=True)
    for name, weapon in database["weapons"].items():
        allowed_weapon = {"name", "type", "subtype", "attacks", "disposition", "reload_time", "magazine_size", "recharge_delay", "recharge_rate", "incarnon_charges", "incarnon_recharge_count", "evolutions", "exalted", "pseudo_exalted", "progenitor", "companion", "combo", "implementation_status"}
        if set(weapon) - allowed_weapon: raise ValueError(f"weapons.{name}: invalid fields {sorted(set(weapon) - allowed_weapon)}")
        _implementation_status(weapon.get("implementation_status"), f"weapons.{name}.implementation_status")
        if weapon.get("name") != name or "ammo" in weapon: raise ValueError(f"weapons.{name}: invalid record")
        if not weapon.get("attacks"): raise ValueError(f"weapons.{name}: attacks are required")
        for attack_name, attack in weapon["attacks"].items():
            if set(attack) - {"trigger", "delivery", "form", "category", "aoe", "children", "stats"}: raise ValueError(f"weapons.{name}.attacks.{attack_name}: invalid fields")
        for tier, choices in weapon.get("evolutions", {}).items():
            for choice, record in choices.items():
                path = f"weapons.{name}.evolutions.{tier}.{choice}"
                if not isinstance(record, dict) or set(record) - {"perk", "description", "values"}: raise ValueError(f"{path}: invalid fields")
                perk_name = record.get("perk")
                if perk_name not in database["perks"]: raise ValueError(f"{path}: unknown perk {perk_name!r}")
                values = record.get("values")
                templates = database["perks"][perk_name].get("stats", {})
                if not isinstance(values, dict): raise ValueError(f"{path}.values: expected an object")
                missing = set(templates) - set(values)
                unknown = set(values) - set(templates)
                if missing: raise ValueError(f"{path}.values: missing stats {sorted(missing)}")
                if unknown: raise ValueError(f"{path}.values: unknown stats {sorted(unknown)}")
                for stat, stat_values in values.items():
                    if not isinstance(stat_values, list) or len(stat_values) != len(templates[stat]): raise ValueError(f"{path}.values.{stat}: expected {len(templates[stat])} values")
                    if any(not isinstance(value, (int, float, bool, str)) or isinstance(value, str) and not value or value == "$weapon" for value in stat_values): raise ValueError(f"{path}.values.{stat}: invalid concrete value")
    for name, upgrade in database["upgrades"].items():
        allowed_upgrade = {"name", "kind", "slot", "max_rank", "implementation_status", "compatibility", "conflicts", "stats", "combos"}
        if set(upgrade) - allowed_upgrade: raise ValueError(f"upgrades.{name}: invalid fields {sorted(set(upgrade) - allowed_upgrade)}")
        _implementation_status(upgrade.get("implementation_status"), f"upgrades.{name}.implementation_status")
        if upgrade.get("name") != name: raise ValueError(f"upgrades.{name}: invalid name")
        if upgrade.get("kind") not in {"mod", "arcane", "buff"}: raise ValueError(f"upgrades.{name}: invalid kind")
        if upgrade.get("slot") not in {"regular_mod", "exilus_mod", "stance_mod", "regular_arcane"}: raise ValueError(f"upgrades.{name}: invalid slot")
        if set(upgrade.get("compatibility", {})) - {"types", "subtypes", "names", "categories", "triggers", "aoe"}: raise ValueError(f"upgrades.{name}.compatibility: invalid fields")
        _effects(upgrade.get("stats", {}), f"upgrades.{name}.stats")
    allowed_enemy = {"name", "faction", "base_level", "stats", "bodyparts", "modifiers"}
    allowed_enemy_stats = {"health", "shields", "armor", "overguard"}
    allowed_bodypart = {"type", "multiplier"}
    for name, enemy in database["enemies"].items():
        path = f"enemies.{name}"
        if not isinstance(enemy, dict): raise ValueError(f"{path}: expected an object")
        if set(enemy) - allowed_enemy: raise ValueError(f"{path}: invalid fields {sorted(set(enemy) - allowed_enemy)}")
        if not isinstance(enemy.get("name"), str) or not enemy["name"]: raise ValueError(f"{path}: invalid name")
        stats = enemy.get("stats")
        if not isinstance(stats, dict) or set(stats) != allowed_enemy_stats: raise ValueError(f"{path}.stats: expected {sorted(allowed_enemy_stats)}")
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0 for value in stats.values()): raise ValueError(f"{path}.stats: values must be finite nonnegative numbers")
        bodyparts = enemy.get("bodyparts")
        if not isinstance(bodyparts, dict) or not bodyparts: raise ValueError(f"{path}.bodyparts: expected a nonempty object")
        for bodypart_name, bodypart in bodyparts.items():
            if not isinstance(bodypart, dict) or set(bodypart) != allowed_bodypart: raise ValueError(f"{path}.bodyparts.{bodypart_name}: invalid fields")
            if bodypart.get("type") not in {"normal", "weakpoint", "resistant"}: raise ValueError(f"{path}.bodyparts.{bodypart_name}.type: invalid type")
            if not isinstance(bodypart.get("multiplier"), (int, float)) or isinstance(bodypart.get("multiplier"), bool) or not isfinite(bodypart["multiplier"]) or bodypart["multiplier"] < 0: raise ValueError(f"{path}.bodyparts.{bodypart_name}.multiplier: expected a finite nonnegative number")
        modifiers = enemy.get("modifiers")
        if not isinstance(modifiers, dict) or not all(isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0 for value in modifiers.values()): raise ValueError(f"{path}.modifiers: expected nonnegative numeric values")
    for category, stats in database["riven_stats"].items():
        path = f"riven_stats.{category}"
        if not isinstance(stats, dict) or not stats: raise ValueError(f"{path}: expected a nonempty object")
        if not all(isinstance(stat, str) and isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0 for stat, value in stats.items()): raise ValueError(f"{path}: expected finite nonnegative numeric stats")
