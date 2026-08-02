from __future__ import annotations

from math import isfinite
from typing import Any

from ..domain.effect_stats import MULTIPLICATIVE_EFFECT_STATS, unclassified_effect_stats
from ..domain.effects import AUTOMATIC_FIELDS, EFFECT_FIELDS, REPEATABLE_AUTOMATIC_FIELDS, Effect, Source


def _validate_automatic(automatic: Any, path: str) -> None:
    if not isinstance(automatic, dict) or not set(automatic) <= AUTOMATIC_FIELDS: raise ValueError(f"{path}: invalid automatic fields")
    for key, value in automatic.items():
        values = value if isinstance(value, list) else [value]
        if isinstance(value, list) and (key not in REPEATABLE_AUTOMATIC_FIELDS or not value): raise ValueError(f"{path}.{key}: invalid repeated values")
        if any(not isinstance(item, (int, float, bool, str)) or isinstance(item, str) and not item for item in values): raise ValueError(f"{path}.{key}: expected scalar values")


def _extra_attack(value: Any, path: str) -> None:
    if not isinstance(value, dict) or set(value) - {"parent", "attack"}: raise ValueError(f"{path}: expected parent and attack fields")
    parent = value.get("parent")
    selector_fields = {"names", "triggers", "deliveries", "forms", "categories", "aoe"}
    if not isinstance(parent, dict) or set(parent) - selector_fields or not parent: raise ValueError(f"{path}.parent: expected an attack selector")
    for field in selector_fields - {"aoe"}:
        selected = parent.get(field)
        if selected is not None and (not isinstance(selected, list) or not selected or any(not isinstance(item, str) or not item for item in selected)): raise ValueError(f"{path}.parent.{field}: expected names")
    if "aoe" in parent and not isinstance(parent["aoe"], bool): raise ValueError(f"{path}.parent.aoe: expected a bool")
    attack = value.get("attack")
    if not isinstance(attack, dict) or set(attack) - {"inherit", "name", "trigger", "delivery", "form", "category", "aoe", "children", "stats"}: raise ValueError(f"{path}.attack: invalid fields")
    if attack.get("inherit") != "$parent": raise ValueError(f"{path}.attack.inherit: expected '$parent'")
    if not isinstance(attack.get("name"), str) or not attack["name"]: raise ValueError(f"{path}.attack.name: expected a name")
    if not isinstance(attack.get("stats", {}), dict): raise ValueError(f"{path}.attack.stats: expected an object")

    def expressions(candidate: object, location: str) -> None:
        if isinstance(candidate, dict) and "source" in candidate:
            try: Source.from_record(candidate)
            except (TypeError, ValueError) as error: raise ValueError(f"{location}: {error}") from error
        elif isinstance(candidate, dict):
            for key, item in candidate.items(): expressions(item, f"{location}.{key}")

    expressions(attack.get("stats", {}), f"{path}.attack.stats")


def _effects(stats: Any, path: str, *, sources: bool = False) -> None:
    if not isinstance(stats, dict): raise ValueError(f"{path}: expected an object")
    for stat, effects in stats.items():
        if not isinstance(effects, list) or not effects: raise ValueError(f"{path}.{stat}: expected effects")
        for index, effect in enumerate(effects):
            location = f"{path}.{stat}[{index}]"
            if not isinstance(effect, dict) or not set(effect) <= EFFECT_FIELDS or "value" not in effect or "automatic" not in effect: raise ValueError(f"{location}: invalid effect fields")
            try: parsed = Effect.from_record(effect)
            except (TypeError, ValueError) as error: raise ValueError(f"{location}: {error}") from error
            if sources and (not isinstance(parsed.value, Source) or not parsed.value.path.startswith("$values.")): raise ValueError(f"{location}: expected a $values source")
            if parsed.mode == "multiplicative" and stat not in MULTIPLICATIVE_EFFECT_STATS: raise ValueError(f"{location}: {stat} does not support multiplicative effects")
            if stat == "extra_attack": _extra_attack(effect["value"], f"{location}.value")
            elif isinstance(effect["value"], (dict, list)) and not sources: raise ValueError(f"{location}: value must be scalar")
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
    allowed_root = {"schema_version", "weapons", "upgrades", "enemies", "riven_stats"}
    missing_root = allowed_root - set(database)
    unexpected_root = set(database) - allowed_root
    if missing_root: raise ValueError(f"database: missing fields {sorted(missing_root)}")
    if unexpected_root: raise ValueError(f"database: unexpected fields {sorted(unexpected_root)}")
    if database.get("schema_version") != 20: raise ValueError("schema version 20 is required")
    for section in ("weapons", "upgrades", "enemies", "riven_stats"):
        if not isinstance(database.get(section), dict): raise ValueError(f"{section}: expected an object")
    upgrade_categories = {"mods", "arcanes", "perks"}
    if set(database["upgrades"]) != upgrade_categories: raise ValueError(f"upgrades: expected categories {sorted(upgrade_categories)}")
    for category in upgrade_categories:
        if not isinstance(database["upgrades"][category], dict): raise ValueError(f"upgrades.{category}: expected an object")
    for name, perk in database["upgrades"]["perks"].items():
        if not isinstance(perk, dict) or set(perk) - {"name", "description", "stats", "implementation_status"}: raise ValueError(f"upgrades.perks.{name}: invalid fields")
        if perk.get("name") != name: raise ValueError(f"upgrades.perks.{name}: invalid name")
        _implementation_status(perk.get("implementation_status"), f"upgrades.perks.{name}.implementation_status")
        _effects(perk.get("stats", {}), f"upgrades.perks.{name}.stats", sources=True)
    weapon_categories = {"primaries", "secondaries", "melees", "archguns"}
    if set(database["weapons"]) != weapon_categories: raise ValueError(f"weapons: expected categories {sorted(weapon_categories)}")
    for category, weapons in database["weapons"].items():
        if not isinstance(weapons, dict): raise ValueError(f"weapons.{category}: expected an object")
        for name, weapon in weapons.items():
            allowed_weapon = {"name", "subtype", "attacks", "disposition", "reload_time", "magazine_size", "recharge_delay", "recharge_rate", "incarnon_charges", "incarnon_recharge_count", "evolutions", "exalted", "pseudo_exalted", "progenitor", "companion", "combo", "implementation_status"}
            if set(weapon) - allowed_weapon: raise ValueError(f"weapons.{category}.{name}: invalid fields {sorted(set(weapon) - allowed_weapon)}")
            _implementation_status(weapon.get("implementation_status"), f"weapons.{category}.{name}.implementation_status")
            if weapon.get("name") != name or "ammo" in weapon: raise ValueError(f"weapons.{category}.{name}: invalid record")
            if not weapon.get("attacks"): raise ValueError(f"weapons.{category}.{name}: attacks are required")
            for attack_name, attack in weapon["attacks"].items():
                if attack.get("name") != attack_name or set(attack) - {"name", "trigger", "delivery", "form", "category", "aoe", "children", "stats"}: raise ValueError(f"weapons.{category}.{name}.attacks.{attack_name}: invalid fields")
            for tier, choices in weapon.get("evolutions", {}).items():
                for choice, record in choices.items():
                    path = f"weapons.{category}.{name}.evolutions.{tier}.{choice}"
                    if not isinstance(record, dict) or set(record) - {"perk", "description", "values"}: raise ValueError(f"{path}: invalid fields")
                    perk_name = record.get("perk")
                    if perk_name not in database["upgrades"]["perks"]: raise ValueError(f"{path}: unknown perk {perk_name!r}")
                    values = record.get("values")
                    templates = database["upgrades"]["perks"][perk_name].get("stats", {})
                    if not isinstance(values, dict): raise ValueError(f"{path}.values: expected an object")
                    missing = set(templates) - set(values)
                    unknown = set(values) - set(templates)
                    if missing: raise ValueError(f"{path}.values: missing stats {sorted(missing)}")
                    if unknown: raise ValueError(f"{path}.values: unknown stats {sorted(unknown)}")
                    for stat, stat_values in values.items():
                        if not isinstance(stat_values, list) or len(stat_values) != len(templates[stat]): raise ValueError(f"{path}.values.{stat}: expected {len(templates[stat])} values")
                        if any(not isinstance(value, (int, float, bool, str)) or isinstance(value, str) and not value for value in stat_values): raise ValueError(f"{path}.values.{stat}: invalid concrete value")
    allowed_upgrade = {"name", "slot", "max_rank", "implementation_status", "compatibility", "conflicts", "stats", "combos"}
    effect_stats: set[str] = set()
    for section, expected_slots in (("mods", {"regular_mod", "exilus_mod", "stance_mod"}), ("arcanes", {"regular_arcane"})):
        for name, upgrade in database["upgrades"][section].items():
            path = f"upgrades.{section}.{name}"
            if set(upgrade) - allowed_upgrade: raise ValueError(f"{path}: invalid fields {sorted(set(upgrade) - allowed_upgrade)}")
            _implementation_status(upgrade.get("implementation_status"), f"{path}.implementation_status")
            if upgrade.get("name") != name: raise ValueError(f"{path}: invalid name")
            if upgrade.get("slot") not in expected_slots: raise ValueError(f"{path}: invalid slot")
            compatibility = upgrade.get("compatibility", {})
            if set(compatibility) - {"types", "subtypes", "names", "categories", "triggers", "aoe"}: raise ValueError(f"{path}.compatibility: invalid fields")
            if "aoe" in compatibility and not isinstance(compatibility["aoe"], bool): raise ValueError(f"{path}.compatibility.aoe: expected a boolean")
            _effects(upgrade.get("stats", {}), f"{path}.stats")
            effect_stats.update(upgrade.get("stats", {}))
    for perk in database["upgrades"]["perks"].values(): effect_stats.update(perk.get("stats", {}))
    unclassified = unclassified_effect_stats(effect_stats)
    if unclassified: raise ValueError(f"unclassified effect stats: {sorted(unclassified)}")
    allowed_enemy = {"name", "faction", "base_level", "stats", "bodyparts", "modifiers"}
    allowed_enemy_stats = {"health", "shields", "armor", "overguard"}
    allowed_bodypart = {"name", "type", "multiplier"}
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
            if bodypart.get("name") != bodypart_name: raise ValueError(f"enemies.{name}.bodyparts.{bodypart_name}: name must match its key")
            if not isinstance(bodypart, dict) or set(bodypart) != allowed_bodypart: raise ValueError(f"{path}.bodyparts.{bodypart_name}: invalid fields")
            if bodypart.get("type") not in {"normal", "weakpoint", "resistant"}: raise ValueError(f"{path}.bodyparts.{bodypart_name}.type: invalid type")
            if not isinstance(bodypart.get("multiplier"), (int, float)) or isinstance(bodypart.get("multiplier"), bool) or not isfinite(bodypart["multiplier"]) or bodypart["multiplier"] < 0: raise ValueError(f"{path}.bodyparts.{bodypart_name}.multiplier: expected a finite nonnegative number")
        modifiers = enemy.get("modifiers")
        if not isinstance(modifiers, dict) or not all(isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0 for value in modifiers.values()): raise ValueError(f"{path}.modifiers: expected nonnegative numeric values")
    for category, stats in database["riven_stats"].items():
        path = f"riven_stats.{category}"
        if not isinstance(stats, dict) or not stats: raise ValueError(f"{path}: expected a nonempty object")
        if not all(isinstance(stat, str) and isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0 for stat, value in stats.items()): raise ValueError(f"{path}: expected finite nonnegative numeric stats")
