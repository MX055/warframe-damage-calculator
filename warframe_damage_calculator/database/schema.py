from __future__ import annotations

from math import isfinite
from typing import Any

from ..domain.effect_stats import MULTIPLICATIVE_EFFECT_STATS, unclassified_effect_stats
from ..domain.effects import AUTOMATIC_FIELDS, EFFECT_FIELDS, REPEATABLE_AUTOMATIC_FIELDS, Effect, Source
from ..domain.generated_attacks import GENERATED_ATTACK_RECORD_FIELDS, GENERATED_ATTACK_STAT, GeneratedAttack
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


def _validate_children_names(children: Any, path: str) -> None:
    if children is None: return
    if not isinstance(children, list): raise ValueError(f"{path}: expected a list of names")
    if any(not isinstance(item, str) or not item or "_" in item for item in children): raise ValueError(f"{path}: expected display names")


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


def _validate_attack_record(attack: Any, path: str) -> None:
    if not isinstance(attack, dict) or set(attack) - ATTACK_RECORD_FIELDS: raise ValueError(f"{path}: invalid fields")
    if "links" in attack: raise ValueError(f"{path}: field 'links' was removed; use children")
    if "rank_scale" in attack: raise ValueError(f"{path}: entry-level rank_scale is not allowed")
    display_name = attack.get("name")
    if not isinstance(display_name, str) or not display_name or "_" in display_name: raise ValueError(f"{path}.name: expected a display name")
    _validate_children_names(attack.get("children"), f"{path}.children")
    if not isinstance(attack.get("stats", {}), dict): raise ValueError(f"{path}.stats: expected an object")
    _validate_attack_expressions(attack.get("stats", {}), f"{path}.stats")
    try: Attack.from_record({key: value for key, value in attack.items() if key in ATTACK_RECORD_FIELDS})
    except (TypeError, ValueError) as error: raise ValueError(f"{path}: {error}") from error


def _validate_generated_attack_record(attack: Any, path: str) -> None:
    if not isinstance(attack, dict): raise ValueError(f"{path}: invalid fields")
    if "links" in attack: raise ValueError(f"{path}: field 'links' was removed; use parent and children")
    if "override" in attack: raise ValueError(f"{path}: field 'override' was removed; use inheritance.override")
    if set(attack) - GENERATED_ATTACK_RECORD_FIELDS: raise ValueError(f"{path}: invalid fields")
    if "rank_scale" in attack: raise ValueError(f"{path}: entry-level rank_scale is not allowed")
    display_name = attack.get("name")
    if not isinstance(display_name, str) or not display_name or "_" in display_name: raise ValueError(f"{path}.name: expected a display name")
    if "parent" not in attack: raise ValueError(f"{path}.parent: expected a parent selector")
    _validate_related_attacks(attack["parent"], f"{path}.parent")
    _validate_children_names(attack.get("children"), f"{path}.children")
    inheritance = attack.get("inheritance")
    if inheritance is not None:
        try: parsed = Inheritance.from_record(inheritance)
        except (TypeError, ValueError) as error: raise ValueError(f"{path}.inheritance: {error}") from error
        if parsed is not None:
            for key, value in parsed.override.items():
                _validate_attack_expressions(value, f"{path}.inheritance.override[{key!r}]")
    if "automatic" in attack: _validate_automatic(attack.get("automatic") or {}, f"{path}.automatic")
    try: GeneratedAttack.from_record(attack)
    except (TypeError, ValueError) as error: raise ValueError(f"{path}: {error}") from error


def _effects(stats: Any, path: str, *, sources: bool = False) -> None:
    if not isinstance(stats, dict): raise ValueError(f"{path}: expected an object")
    for stat, effects in stats.items():
        if not isinstance(effects, list) or not effects: raise ValueError(f"{path}.{stat}: expected effects")
        for index, effect in enumerate(effects):
            location = f"{path}.{stat}[{index}]"
            if stat == GENERATED_ATTACK_STAT:
                _validate_generated_attack_record(effect, location)
                continue
            if not isinstance(effect, dict) or not set(effect) <= EFFECT_FIELDS | {"rank_scale"} or "value" not in effect or "automatic" not in effect: raise ValueError(f"{location}: invalid effect fields")
            if "rank_scale" in effect: raise ValueError(f"{location}: entry-level rank_scale is not allowed; wrap individual numeric values")
            try: parsed = Effect.from_record(effect)
            except (TypeError, ValueError) as error: raise ValueError(f"{location}: {error}") from error
            if sources:
                if not isinstance(parsed.value, Source) or not parsed.value.path.startswith("$stats."):
                    raise ValueError(f"{location}: expected a $stats source")
                expected_prefix = f"$stats.{stat}."
                if not parsed.value.path.startswith(expected_prefix) or parsed.value.path == expected_prefix:
                    raise ValueError(f"{location}: expected named source {expected_prefix}<key>")
                key = parsed.value.path[len(expected_prefix):]
                if "." in key or "[" in key or not key:
                    raise ValueError(f"{location}: stats key must be a single path segment")
                if parsed.value.default != 0:
                    raise ValueError(f"{location}: stats sources require default 0")
            if parsed.mode == "multiplicative" and stat not in MULTIPLICATIVE_EFFECT_STATS: raise ValueError(f"{location}: {stat} does not support multiplicative effects")
            if isinstance(effect["value"], dict) and "source" not in effect["value"] and not is_scaled_value_record(effect["value"]): raise ValueError(f"{location}: value must be scalar, scaled value, or source")
            elif isinstance(effect["value"], list): raise ValueError(f"{location}: value must be scalar")
            _validate_automatic(effect["automatic"], f"{location}.automatic")


def _validate_description(value: Any, path: str) -> None:
    if value is not None and not isinstance(value, str): raise ValueError(f"{path}: expected a string")


def _validate_perk_description(value: Any, path: str) -> None:
    if value != "$description": raise ValueError(f"{path}: expected '$description'")


def _validate_perk_stats(value: Any, path: str) -> None:
    if value != "$stats": raise ValueError(f"{path}: expected '$stats'")


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
    if database.get("schema_version") != 28: raise ValueError("schema version 28 is required")
    for section in ("weapons", "upgrades", "enemies", "riven_stats"):
        if not isinstance(database.get(section), dict): raise ValueError(f"{section}: expected an object")
    upgrade_categories = {"mods", "arcanes", "perks"}
    if set(database["upgrades"]) != upgrade_categories: raise ValueError(f"upgrades: expected categories {sorted(upgrade_categories)}")
    for category in upgrade_categories:
        if not isinstance(database["upgrades"][category], dict): raise ValueError(f"upgrades.{category}: expected an object")
    for name, perk in database["upgrades"]["perks"].items():
        if not isinstance(perk, dict) or set(perk) - {"name", "description", "slot_type", "stats", "implementation_status"}: raise ValueError(f"upgrades.perks.{name}: invalid fields")
        if perk.get("name") != name: raise ValueError(f"upgrades.perks.{name}: invalid name")
        if perk.get("slot_type") != "perk": raise ValueError(f"upgrades.perks.{name}: invalid slot_type")
        _validate_perk_description(perk.get("description"), f"upgrades.perks.{name}.description")
        _validate_perk_stats(perk.get("stats"), f"upgrades.perks.{name}.stats")
        _implementation_status(perk.get("implementation_status"), f"upgrades.perks.{name}.implementation_status")
    weapon_categories = {"primaries", "secondaries", "melees", "archguns"}
    if set(database["weapons"]) != weapon_categories: raise ValueError(f"weapons: expected categories {sorted(weapon_categories)}")
    effect_stats: set[str] = set()
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
                _validate_attack_record(attack, f"weapons.{category}.{name}.attacks.{attack_name}")
                if "trigger" not in attack or "delivery" not in attack: raise ValueError(f"weapons.{category}.{name}.attacks.{attack_name}: trigger and delivery are required")
            for tier, choices in weapon.get("evolutions", {}).items():
                for perk_name, record in choices.items():
                    path = f"weapons.{category}.{name}.evolutions.{tier}.{perk_name}"
                    if not isinstance(record, dict) or set(record) - {"description", "stats"}: raise ValueError(f"{path}: invalid fields")
                    if "values" in record: raise ValueError(f"{path}: field 'values' was renamed to 'stats'")
                    if "perk" in record: raise ValueError(f"{path}: perk name is the evolution key; remove 'perk' field")
                    if perk_name not in database["upgrades"]["perks"]: raise ValueError(f"{path}: unknown perk {perk_name!r}")
                    stats = record.get("stats", {})
                    if not isinstance(stats, dict): raise ValueError(f"{path}.stats: expected an object")
                    if stats:
                        _effects(stats, f"{path}.stats", sources=False)
                    effect_stats.update(stats)
                    for stat, effects in stats.items():
                        if not effects:
                            raise ValueError(f"{path}.stats.{stat}: omit empty effect lists")
                        for index, effect in enumerate(effects):
                            value = effect.get("value")
                            if value == 0 or value == 0.0:
                                raise ValueError(f"{path}.stats.{stat}[{index}]: omit zero-valued entries")
    allowed_mod = {"name", "description", "slot_type", "max_rank", "implementation_status", "compatibility", "conflicts", "stats", "combos"}
    allowed_arcane = {"name", "description", "slot_type", "max_rank", "implementation_status", "compatibility", "conflicts", "stats"}
    for section, expected_slots, allowed_upgrade in (("mods", {"regular_mod", "exilus_mod", "stance_mod"}, allowed_mod), ("arcanes", {"regular_arcane"}, allowed_arcane)):
        for name, upgrade in database["upgrades"][section].items():
            path = f"upgrades.{section}.{name}"
            if set(upgrade) - allowed_upgrade: raise ValueError(f"{path}: invalid fields {sorted(set(upgrade) - allowed_upgrade)}")
            _implementation_status(upgrade.get("implementation_status"), f"{path}.implementation_status")
            if upgrade.get("name") != name: raise ValueError(f"{path}: invalid name")
            _validate_description(upgrade.get("description"), f"{path}.description")
            if upgrade.get("slot_type") not in expected_slots: raise ValueError(f"{path}: invalid slot_type")
            compatibility = upgrade.get("compatibility", {})
            if set(compatibility) - {"types", "subtypes", "names", "categories", "triggers", "aoe"}: raise ValueError(f"{path}.compatibility: invalid fields")
            if "aoe" in compatibility and not isinstance(compatibility["aoe"], bool): raise ValueError(f"{path}.compatibility.aoe: expected a boolean")
            _effects(upgrade.get("stats", {}), f"{path}.stats")
            if section == "mods": _validate_combos(upgrade.get("combos"), f"{path}.combos")
            effect_stats.update(upgrade.get("stats", {}))
    unclassified = unclassified_effect_stats(effect_stats)
    if unclassified: raise ValueError(f"unclassified effect stats: {sorted(unclassified)}")
    allowed_enemy = {"name", "faction", "base_level", "stats", "body_parts", "modifiers"}
    allowed_enemy_stats = {"health", "shields", "armor", "overguard"}
    allowed_body_part = {"name", "type", "multiplier"}
    for name, enemy in database["enemies"].items():
        path = f"enemies.{name}"
        if not isinstance(enemy, dict): raise ValueError(f"{path}: expected an object")
        if set(enemy) - allowed_enemy: raise ValueError(f"{path}: invalid fields {sorted(set(enemy) - allowed_enemy)}")
        if not isinstance(enemy.get("name"), str) or not enemy["name"]: raise ValueError(f"{path}: invalid name")
        stats = enemy.get("stats")
        if not isinstance(stats, dict) or set(stats) != allowed_enemy_stats: raise ValueError(f"{path}.stats: expected {sorted(allowed_enemy_stats)}")
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0 for value in stats.values()): raise ValueError(f"{path}.stats: values must be finite nonnegative numbers")
        body_parts = enemy.get("body_parts")
        if not isinstance(body_parts, dict) or not body_parts: raise ValueError(f"{path}.body_parts: expected a nonempty object")
        for body_part_name, body_part in body_parts.items():
            if not isinstance(body_part, dict) or set(body_part) != allowed_body_part: raise ValueError(f"{path}.body_parts.{body_part_name}: invalid fields")
            display_name = body_part.get("name")
            if not isinstance(display_name, str) or not display_name or "_" in display_name: raise ValueError(f"{path}.body_parts.{body_part_name}.name: expected a display name")
            if body_part.get("type") not in {"normal", "weak_point", "resistant"}: raise ValueError(f"{path}.body_parts.{body_part_name}.type: invalid type")
            if not isinstance(body_part.get("multiplier"), (int, float)) or isinstance(body_part.get("multiplier"), bool) or not isfinite(body_part["multiplier"]) or body_part["multiplier"] < 0: raise ValueError(f"{path}.body_parts.{body_part_name}.multiplier: expected a finite nonnegative number")
        modifiers = enemy.get("modifiers")
        if not isinstance(modifiers, dict) or not all(isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0 for value in modifiers.values()): raise ValueError(f"{path}.modifiers: expected nonnegative numeric values")
    for category, stats in database["riven_stats"].items():
        path = f"riven_stats.{category}"
        if not isinstance(stats, dict) or not stats: raise ValueError(f"{path}: expected a nonempty object")
        if not all(isinstance(stat, str) and isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0 for stat, value in stats.items()): raise ValueError(f"{path}: expected finite nonnegative numeric stats")
