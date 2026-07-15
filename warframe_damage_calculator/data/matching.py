from typing import Any

from .normalization import as_list, normalize_identifier
from .schema import DatabaseEntry


PRIMARY_TYPES = frozenset({"primary", "rifle", "bow", "shotgun", "sniper"})
SECONDARY_TYPES = frozenset({"secondary", "pistol"})
MELEE_TYPES = frozenset({"melee"})

_FILTER_ALIASES = {
    "weapons": "weapon",
    "primaries": "primary",
    "secondaries": "secondary",
    "pistols": "secondary",
    "melees": "melee",
    "upgrades": "upgrade",
    "mods": "mod",
    "arcanes": "arcane",
}

_TYPE_ALIASES = {
    "primary": PRIMARY_TYPES,
    "secondary": SECONDARY_TYPES,
    "pistol": frozenset({"pistol"}),
    "melee": MELEE_TYPES,
}


def normalize_filter(value: Any) -> str | None:
    if value is None:
        return None
    key = normalize_identifier(value)
    return _FILTER_ALIASES.get(key, key)


def expand_type_filter(value: Any) -> set[str]:
    if value is None:
        return set()
    key = normalize_identifier(value)
    return set(_TYPE_ALIASES.get(key, {key}))


def _normalized_values(value: Any) -> set[str]:
    return {normalize_identifier(item) for item in as_list(value)}


def _requirements_match_type(requirements: dict[str, Any], requested: set[str]) -> bool:
    for key, value in requirements.items():
        if normalize_identifier(key) in requested:
            return True
        if _normalized_values(value) & requested:
            return True
    return False


def weapon_matches(entry: DatabaseEntry, item_type: str | None) -> bool:
    item_type = normalize_filter(item_type)
    if item_type is None or item_type == "weapon":
        return True
    if item_type in {"upgrade", "mod", "arcane"}:
        return False

    if item_type in {"primary", "secondary", "melee"}:
        return entry.category == item_type

    requested = expand_type_filter(item_type)
    context = entry.data.get("context", entry.data)
    weapon_type = normalize_identifier(context.get("type"))
    trigger = normalize_identifier(context.get("trigger"))
    return weapon_type in requested or trigger in requested


def upgrade_matches(entry: DatabaseEntry, item_type: str | None) -> bool:
    item_type = normalize_filter(item_type)
    if item_type is None or item_type == "upgrade":
        return True
    if item_type in {"mod", "arcane"}:
        return entry.category == item_type
    if item_type == "weapon":
        return False

    requested = expand_type_filter(item_type)
    context = entry.data.get("context", entry.data)
    compatibility = _normalized_values(context.get("compatibility"))

    if item_type == "primary" and compatibility & PRIMARY_TYPES:
        return True
    if item_type == "secondary" and compatibility & SECONDARY_TYPES:
        return True
    if item_type == "melee" and compatibility & MELEE_TYPES:
        return True

    requirements = context.get("requirements") or {}
    return bool(compatibility & requested) or _requirements_match_type(requirements, requested)


def entry_matches(entry: DatabaseEntry, item_type: str | None) -> bool:
    if entry.is_weapon:
        return weapon_matches(entry, item_type)
    return upgrade_matches(entry, item_type)
