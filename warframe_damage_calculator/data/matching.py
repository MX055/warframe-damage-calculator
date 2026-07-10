from __future__ import annotations

from typing import Any, Iterable

from ..utils import MELEE_TYPES, PRIMARY_TYPES, SECONDARY_TYPES, TYPE_ALIASES
from .normalization import as_list, normalized_slug


class DatabaseMatchingMixin:
    def _expanded_type_filter(self, value: str | Iterable[str] | None) -> set[str]:
        if value is None:
            return set()

        raw_values = as_list(value)
        result: set[str] = set()

        for raw in raw_values:
            key = normalized_slug(raw)
            result.update(TYPE_ALIASES.get(key, {key}))

        return result

    def _weapon_matches_type(self, section: str, weapon: dict[str, Any], requested: set[str]) -> bool:
        if not requested:
            return True

        weapon_type = normalized_slug(weapon.get("type"))

        if section == "primaries" and requested & PRIMARY_TYPES:
            if requested & {"primary"}:
                return True
            return weapon_type in requested

        if section == "secondaries" and requested & SECONDARY_TYPES:
            if requested & {"secondary"}:
                return True
            return weapon_type in requested

        if section == "melees" and requested & MELEE_TYPES:
            if requested & {"melee"}:
                return True
            return weapon_type in requested

        return weapon_type in requested

    def _upgrade_matches_type(self, upgrade: dict[str, Any], requested: set[str]) -> bool:
        if not requested:
            return True

        compatibility = {normalized_slug(item) for item in upgrade.get("compatibility", [])}
        
        if "pistol" in requested and "pistol" in compatibility:
            return True

        if "primary" in requested and compatibility & PRIMARY_TYPES:
            return True

        return bool(compatibility & requested)

    def _upgrade_matches_weapon(self, upgrade: dict[str, Any], weapon_name: str, weapon: dict[str, Any], weapon_section: str) -> bool:
        compatibility = {normalized_slug(item) for item in upgrade.get("compatibility", [])}

        weapon_name_key = normalized_slug(weapon_name)
        weapon_type = normalized_slug(weapon.get("type"))

        if weapon_section == "primaries":
            weapon_family = "primary"
        elif weapon_section == "secondaries":
            weapon_family = "pistol"
        elif weapon_section == "melees":
            weapon_family = "melee"
        else:
            weapon_family = ""

        compatible = weapon_name_key in compatibility or weapon_type in compatibility or weapon_family in compatibility

        if not compatible:
            return False

        return self._requirements_match(weapon, upgrade.get("requirements") or {})

    def _requirements_match(self, weapon: dict[str, Any], requirements: dict[str, Any]) -> bool:
        if not requirements:
            return True

        for key, expected in requirements.items():
            key = normalized_slug(key)

            if key == "trigger":
                allowed = {normalized_slug(v) for v in as_list(expected)}
                if normalized_slug(weapon.get("trigger")) not in allowed:
                    return False

            elif key == "type":
                allowed = {normalized_slug(v) for v in as_list(expected)}
                if normalized_slug(weapon.get("type")) not in allowed:
                    return False

            elif key in {"is_beam", "is_battery"}:
                if bool(weapon.get(key)) != bool(expected):
                    return False

            elif key.startswith("min_"):
                field = key.removeprefix("min_")
                if float(weapon.get(field, 0) or 0) < float(expected):
                    return False

            elif key.startswith("max_"):
                field = key.removeprefix("max_")
                if float(weapon.get(field, 0) or 0) > float(expected):
                    return False

            else:
                if key not in weapon:
                    return False
                if weapon.get(key) != expected:
                    return False

        return True



