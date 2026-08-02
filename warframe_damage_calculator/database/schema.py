from __future__ import annotations

from math import isfinite
from typing import Any

from ..domain.effect_stats import MULTIPLICATIVE_EFFECT_STATS, unclassified_effect_stats
from ..domain.effects import AUTOMATIC_FIELDS, EFFECT_FIELDS, REPEATABLE_AUTOMATIC_FIELDS, Effect, Source
from ..domain.generated_attacks import GENERATED_ATTACK_STAT
from ..domain.scaled_values import is_scaled_value_record, UpgradeValue
from ..domain.attacks import ATTACK_RECORD_FIELDS, Inheritance, RelatedAttacks, Attack
from ..domain.upgrades import COMBO_FIELDS, Combo


def _validate_scaled_value(value: Any, path: str) -> None:
    try: UpgradeValue.from_record(value)
    except (TypeError, ValueError) as error: raise ValueError(f"{path}: {error}") from error


def _validate_numeric_or_scaled(value: Any, path: str) -> None:
    if is_scaled_value_record(value):
        _validate_scaled_value(value, path)
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)): raise ValueError(f"{path}: expected a number or scaled value")


def _validate_automatic(automatic: Any, path: str) -> None:
    if not isinstance(automatic, dict) or not set(automatic) <= AUTOMATIC_FIELDS: raise ValueError(f"{path}: invalid automatic fields")
    for key, value in automatic.items():
        if key in {"chance", "for", "per", "multiply", "stacks"} and not isinstance(value, list):
            if isinstance(value, (int, float, bool)) or is_scaled_value_record(value):
                if is_scaled_value_record(value): _validate_scaled_value(value, f"{path}.{key}")
                continue
        values = value if isinstance(value, list) else [value]
        if isinstance(value, list) and (key not in REPEATABLE_AUTOMATIC_FIELDS or not value): raise ValueError(f"{path}.{key}: invalid repeated values")
        for index, item in enumerate(values):
            if is_scaled_value_record(item):
                _validate_scaled_value(item, f"{path}.{key}[{index}]")
            elif not isinstance(item, (int, float, bool, str)) or isinstance(item, str) and not item:
                raise ValueError(f"{path}.{key}: expected scalar values")


def _validate_source_expression(value: Any, path: str) -> None:
    try: Source.from_record(value)
    except (TypeError, ValueError) as error: raise ValueError(f"{path}: {error}") from error


def _validate_attack_expressions(candidate: object, location: str) -> None:
    if isinstance(candidate, dict) and "source" in candidate:
        _validate_source_expression(candidate, location)
        multiplier = candidate.get("multiplier", 1)
        if is_scaled_value_record(multiplier): _validate_scaled_value(multiplier, f"{location}.multiplier")
    elif is_scaled_value_record(candidate):
        _validate_scaled_value(candidate, location)
    elif isinstance(candidate, dict):
        for key, item in candidate.items(): _validate_attack_expressions(item, f"{location}.{key}")


def _validate_related_attacks(related: Any, path: str, *, display_names: bool = False) -> None:
    try: parsed = RelatedAttacks.from_record(related)
    except (TypeError, ValueError) as error: raise ValueError(f"{path}: {error}") from error
    if display_names and parsed.names is not None and any("_" in name for name in parsed.names):
        raise ValueError(f"{path}.names: expected display names")


def _validate_links(links: Any, path: str, *, require_parents: bool = False, display_child_names: bool = False) -> None:
    if links is None: return
    if not isinstance(links, dict) or set(links) - {"parents", "children"}: raise ValueError(f"{path}: invalid links fields")
    if "parents" in links:
        if require_parents and not links["parents"]: raise ValueError(f"{path}.parents: expected a parent selector")
        _validate_related_attacks(links["parents"], f"{path}.parents")
    elif require_parents:
        raise ValueError(f"{path}.parents: expected a parent selector")
    if "children" in links:
        _validate_related_attacks(links["children"], f"{path}.children", display_names=display_child_names)


def _validate_combos(combos: Any, path: str) -> None:
    if combos is None: return
    if not isinstance(combos, dict): raise ValueError(f"{path}: expected an object")
    seen_types: set[str] = set()
    for combo_id, record in combos.items():
        location = f"{path}.{combo_id}"
        if not isinstance(combo_id, str) or not combo_id or any(ch == " " or ch.isupper() for ch in combo_id): raise ValueError(f"{location}: expected a snake_case id")
        try: combo = Combo.from_record(record)
        except (TypeError, ValueError) as error: raise ValueError(f"{location}: {error}") from error
        if combo.type in seen_types: raise ValueError(f"{path}: duplicate combo type {combo.type!r}")
        seen_types.add(combo.type)
        if set(record) - COMBO_FIELDS: raise ValueError(f"{location}: invalid fields")


def _validate_attack_record(attack: Any, path: str, *, generated: bool = False) -> None:
    if not isinstance(attack, dict) or set(attack) - ATTACK_RECORD_FIELDS: raise ValueError(f"{path}: invalid fields")
    if "rank_scale" in attack: raise ValueError(f"{path}: entry-level rank_scale is not allowed")
    display_name = attack.get("name")
    if not isinstance(display_name, str) or not display_name or "_" in display_name: raise ValueError(f"{path}.name: expected a display name")
    inheritance = attack.get("inheritance")
    if inheritance is not None:
        try: Inheritance.from_record(inheritance)
        except (TypeError, ValueError) as error: raise ValueError(f"{path}.inheritance: {error}") from error
    _validate_links(attack.get("links"), f"{path}.links", require_parents=generated, display_child_names=not generated)
    if generated and not attack.get("links", {}).get("parents"): raise ValueError(f"{path}.links.parents: expected at least one parent selector")
    if "automatic" in attack: _validate_automatic(attack.get("automatic") or {}, f"{path}.automatic")
    if not isinstance(attack.get("stats", {}), dict): raise ValueError(f"{path}.stats: expected an object")
    _validate_attack_expressions(attack.get("stats", {}), f"{path}.stats")
    try: Attack.from_record({key: value for key, value in attack.items() if key in ATTACK_RECORD_FIELDS})
    except (TypeError, ValueError) as error: raise ValueError(f"{path}: {error}") from error


def _effects(stats: Any, path: str, *, sources: bool = False) -> None:
    if not isinstance(stats, dict): raise ValueError(f"{path}: expected an object")
    for stat, effects in stats.items():
        if not isinstance(effects, list) or not effects: raise ValueError(f"{path}.{stat}: expected effects")
        for index, effect in enumerate(effects):
            location = f"{path}.{stat}[{index}]"
            if stat == GENERATED_ATTACK_STAT:
                _validate_attack_record(effect, location, generated=True)
                continue
            if not isinstance(effect, dict) or not set(effect) <= EFFECT_FIELDS | {"rank_scale"} or "value" not in effect or "automatic" not in effect: raise ValueError(f"{location}: invalid effect fields")
            if "rank_scale" in effect: raise ValueError(f"{location}: entry-level rank_scale is not allowed; wrap individual numeric values")
            try: parsed = Effect.from_record(effect)
            except (TypeError, ValueError) as error: raise ValueError(f"{location}: {error}") from error
            if sources and (not isinstance(parsed.value, Source) or not parsed.value.path.startswith("$values.")): raise ValueError(f"{location}: expected a $values source")
            if parsed.mode == "multiplicative" and stat not in MULTIPLICATIVE_EFFECT_STATS: raise ValueError(f"{location}: {stat} does not support multiplicative effects")
            if isinstance(effect["value"], dict) and "source" not in effect["value"] and not is_scaled_value_record(effect["value"]): raise ValueError(f"{location}: value must be scalar, scaled value, or source")
            elif isinstance(effect["value"], list): raise ValueError(f"{location}: value must be scalar")
            _validate_automatic(effect["automatic"], f"{location}.automatic")


def _validate_description(value: Any, path: str) -> None:
    if value is not None and not isinstance(value, str): raise ValueError(f"{path}: expected a string")


def _validate_perk_description(value: Any, path: str) -> None:
    if not isinstance(value, dict): raise ValueError(f"{path}: expected a source expression")
    try:
        source = Source.from_record(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{path}: {error}") from error
    if source.path != "$description": raise ValueError(f"{path}: expected source '$description'")


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
    if database.get("schema_version") != 24: raise ValueError("schema version 24 is required")
    for section in ("weapons", "upgrades", "enemies", "riven_stats"):
        if not isinstance(database.get(section), dict): raise ValueError(f"{section}: expected an object")
    upgrade_categories = {"mods", "arcanes", "perks"}
    if set(database["upgrades"]) != upgrade_categories: raise ValueError(f"upgrades: expected categories {sorted(upgrade_categories)}")
    for category in upgrade_categories:
        if not isinstance(database["upgrades"][category], dict): raise ValueError(f"upgrades.{category}: expected an object")
    for name, perk in database["upgrades"]["perks"].items():
        if not isinstance(perk, dict) or set(perk) - {"name", "description", "stats", "implementation_status"}: raise ValueError(f"upgrades.perks.{name}: invalid fields")
        if perk.get("name") != name: raise ValueError(f"upgrades.perks.{name}: invalid name")
        _validate_perk_description(perk.get("description"), f"upgrades.perks.{name}.description")
        _implementation_status(perk.get("implementation_status"), f"upgrades.perks.{name}.implementation_status")
        _effects(perk.get("stats", {}), f"upgrades.perks.{name}.stats", sources=True)
    weapon_categories = {"primaries", "secondaries", "melees", "archguns"}
    if set(database["weapons"]) != weapon_categories: raise ValueError(f"weapons: expected categories {sorted(weapon_categories)}")
    for category, weapons in database["weapons"].items():
        if not isinstance(weapons, dict): raise ValueError(f"weapons.{category}: expected an object")
        for name, weapon in weapons.items():
            allowed_weapon = {"name", "description", "subtype", "attacks", "disposition", "reload_time", "magazine_size", "recharge_delay", "recharge_rate", "incarnon_charges", "incarnon_recharge_count", "evolutions", "exalted", "pseudo_exalted", "progenitor", "companion", "combo", "implementation_status"}
            if set(weapon) - allowed_weapon: raise ValueError(f"weapons.{category}.{name}: invalid fields {sorted(set(weapon) - allowed_weapon)}")
            _validate_description(weapon.get("description"), f"weapons.{category}.{name}.description")
            _implementation_status(weapon.get("implementation_status"), f"weapons.{category}.{name}.implementation_status")
            if weapon.get("name") != name or "ammo" in weapon: raise ValueError(f"weapons.{category}.{name}: invalid record")
            if not weapon.get("attacks"): raise ValueError(f"weapons.{category}.{name}: attacks are required")
            for attack_name, attack in weapon["attacks"].items():
                _validate_attack_record(attack, f"weapons.{category}.{name}.attacks.{attack_name}", generated=False)
                if "trigger" not in attack or "delivery" not in attack: raise ValueError(f"weapons.{category}.{name}.attacks.{attack_name}: trigger and delivery are required")
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
    allowed_upgrade = {"name", "description", "slot", "max_rank", "implementation_status", "compatibility", "conflicts", "stats", "combos"}
    effect_stats: set[str] = set()
    for section, expected_slots in (("mods", {"regular_mod", "exilus_mod", "stance_mod"}), ("arcanes", {"regular_arcane"})):
        for name, upgrade in database["upgrades"][section].items():
            path = f"upgrades.{section}.{name}"
            if set(upgrade) - allowed_upgrade: raise ValueError(f"{path}: invalid fields {sorted(set(upgrade) - allowed_upgrade)}")
            _implementation_status(upgrade.get("implementation_status"), f"{path}.implementation_status")
            if upgrade.get("name") != name: raise ValueError(f"{path}: invalid name")
            _validate_description(upgrade.get("description"), f"{path}.description")
            if upgrade.get("slot") not in expected_slots: raise ValueError(f"{path}: invalid slot")
            compatibility = upgrade.get("compatibility", {})
            if set(compatibility) - {"types", "subtypes", "names", "categories", "triggers", "aoe"}: raise ValueError(f"{path}.compatibility: invalid fields")
            if "aoe" in compatibility and not isinstance(compatibility["aoe"], bool): raise ValueError(f"{path}.compatibility.aoe: expected a boolean")
            _effects(upgrade.get("stats", {}), f"{path}.stats")
            _validate_combos(upgrade.get("combos"), f"{path}.combos")
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
            if not isinstance(bodypart, dict) or set(bodypart) != allowed_bodypart: raise ValueError(f"{path}.bodyparts.{bodypart_name}: invalid fields")
            display_name = bodypart.get("name")
            if not isinstance(display_name, str) or not display_name or "_" in display_name: raise ValueError(f"{path}.bodyparts.{bodypart_name}.name: expected a display name")
            if bodypart.get("type") not in {"normal", "weakpoint", "resistant"}: raise ValueError(f"{path}.bodyparts.{bodypart_name}.type: invalid type")
            if not isinstance(bodypart.get("multiplier"), (int, float)) or isinstance(bodypart.get("multiplier"), bool) or not isfinite(bodypart["multiplier"]) or bodypart["multiplier"] < 0: raise ValueError(f"{path}.bodyparts.{bodypart_name}.multiplier: expected a finite nonnegative number")
        modifiers = enemy.get("modifiers")
        if not isinstance(modifiers, dict) or not all(isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0 for value in modifiers.values()): raise ValueError(f"{path}.modifiers: expected nonnegative numeric values")
    for category, stats in database["riven_stats"].items():
        path = f"riven_stats.{category}"
        if not isinstance(stats, dict) or not stats: raise ValueError(f"{path}: expected a nonempty object")
        if not all(isinstance(stat, str) and isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0 for stat, value in stats.items()): raise ValueError(f"{path}: expected finite nonnegative numeric stats")
