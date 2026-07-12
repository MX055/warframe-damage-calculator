from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..models import Upgrade, Primary, Secondary, Melee, dist
from ..utils import DAMAGE_TYPES, COMMON_WEAPON_PAYLOAD_FIELDS, RANGED_WEAPON_PAYLOAD_FIELDS, MELEE_WEAPON_PAYLOAD_FIELDS, WEAPON_DIST_FIELDS
from .normalization import normalized_slug


class DatabaseConstructionMixin:
    def _weapon_model_class(self, section: str) -> type:
        if section == "primaries":
            return Primary
        if section == "secondaries":
            return Secondary
        if section == "melees":
            return Melee
        raise ValueError(f"Unknown weapon section: {section!r}")

    def _make_dist_object(self, values: dict[str, Any] | None) -> dist:
        clean_values: dict[str, Any] = {}

        for key, value in (values or {}).items():
            damage_key = normalized_slug(key)
            if damage_key in DAMAGE_TYPES and value not in (None, 0, 0.0):
                clean_values[damage_key] = value

        try:
            return dist(**clean_values)
        except TypeError:
            pass

        try:
            return dist(clean_values)
        except TypeError:
            pass

        obj = dist()
        for key, value in clean_values.items():
            try:
                setattr(obj, key, value)
            except Exception:
                pass
        return obj

    def _weapon_payload_fields(self, section: str) -> set[str]:
        if section in {"primaries", "secondaries"}:
            return RANGED_WEAPON_PAYLOAD_FIELDS
        if section == "melees":
            return MELEE_WEAPON_PAYLOAD_FIELDS
        return COMMON_WEAPON_PAYLOAD_FIELDS

    def _prepare_weapon_payload(self, section: str, name: str, data: dict[str, Any]) -> dict[str, Any]:
        allowed_fields = self._weapon_payload_fields(section)
        source = deepcopy(data)
        source.setdefault("name", name)

        payload = {field_name: value for field_name, value in source.items() if field_name in allowed_fields}

        for field_name in WEAPON_DIST_FIELDS:
            if field_name in allowed_fields:
                payload[field_name] = self._make_dist_object(payload.get(field_name) or {})

        return payload

    def _prepare_upgrade_metadata(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert database metadata into the types used by ``Upgrade``."""
        return {
            "compatibility": set(data.get("compatibility") or ()),
            "incompatibility": set(data.get("incompatibility") or ()),
            "requirements": deepcopy(data.get("requirements") or {}),
            "max_rank": data.get("max_rank"),
            "max_stacks": data.get("max_stacks"),
            "is_exilus": bool(data.get("is_exilus", False)),
        }

    def _prepare_upgrade_payload(self, data: dict[str, Any], *, section: str | None = None) -> dict[str, Any]:
        conditions = data.get("conditions") or {}
        fallback_condition = data.get("condition") or "condition"
        payload = self._prepare_upgrade_metadata(data)
        payload.update({
            "stats": deepcopy(data.get("stats") or {}),
            "conditional_stats": {
                stat: (value, conditions.get(stat, fallback_condition))
                for stat, value in (data.get("conditionals") or {}).items()
            },
            "stacking_stats": {
                stat: (value, conditions.get(stat, data.get("condition") or "stacks"))
                for stat, value in (data.get("stackables") or {}).items()
            },
        })
        if section == "mods":
            payload["category"] = "mod"
        elif section == "arcanes":
            payload["category"] = "arcane"
        return payload

    def _make_weapon_object(self, section: str, name: str, data: dict[str, Any]) -> Primary | Secondary | Melee:
        payload = self._prepare_weapon_payload(section, name, data)
        return self._construct_object(self._weapon_model_class(section), name, payload)

    def _make_upgrade_object(self, name: str, data: dict[str, Any], *, section: str | None = None) -> Upgrade:
        payload = self._prepare_upgrade_payload(data, section=section)
        return self._construct_object(Upgrade, name, payload)

    def _make_upgrade_bucket_object(self, name: str, data: dict[str, Any], *, section: str | None = None, bucket: str = "stats") -> Upgrade:
        raw_bucket = deepcopy(data.get(bucket) or {})
        payload = self._prepare_upgrade_metadata(data)
        payload["stats"] = raw_bucket
        if section == "mods":
            payload["category"] = "mod"
        elif section == "arcanes":
            payload["category"] = "arcane"
        return self._construct_object(Upgrade, name, payload)

    def _construct_object(self, cls: type, name: str, data: dict[str, Any]) -> Any:
        payload = deepcopy(data)
        payload.setdefault("name", name)

        try:
            return cls(**payload)
        except TypeError as exc:
            raise TypeError(
                f"Could not construct {cls.__name__} object for {name!r}. "
                f"Check that the JSON keys match the {cls.__name__} constructor."
            ) from exc
