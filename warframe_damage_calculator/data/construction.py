from __future__ import annotations

from copy import deepcopy
from inspect import Parameter, signature
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

    def _resolve_stack_count(self, data: dict[str, Any], stacks: int | None) -> int:
        """Use max_stacks by default, otherwise use the explicit stack count."""
        if stacks is None:
            stacks = data.get("max_stacks") or 0

        try:
            stack_count = int(stacks)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"stacks must be an int or None, got {stacks!r}") from exc

        if stack_count < 0:
            raise ValueError("stacks must be >= 0")

        return stack_count

    def _scale_stat_bucket(self, bucket: dict[str, Any], multiplier: int | float) -> dict[str, Any]:
        scaled: dict[str, Any] = {}

        for key, value in (bucket or {}).items():
            if isinstance(value, bool):
                scaled[key] = value
            elif isinstance(value, int | float):
                scaled[key] = value * multiplier
            else:
                scaled[key] = value

        return scaled

    def _merge_stat_buckets(self, *buckets: dict[str, Any]) -> dict[str, Any]:
        merged: dict[str, Any] = {}

        for bucket in buckets:
            for key, value in (bucket or {}).items():
                if isinstance(value, bool):
                    merged[key] = bool(merged.get(key, False)) or value
                elif isinstance(value, int | float) and isinstance(merged.get(key), int | float) and not isinstance(merged.get(key), bool):
                    merged[key] += value
                else:
                    merged[key] = value

        return merged

    def _effective_upgrade_bucket(self, data: dict[str, Any], *, stacks: int | None, condition: bool) -> dict[str, Any]:
        stack_count = self._resolve_stack_count(data, stacks)

        buckets: list[dict[str, Any]] = [deepcopy(data.get("stats") or {})]

        if condition:
            buckets.append(deepcopy(data.get("conditionals") or {}))

        if stack_count:
            buckets.append(self._scale_stat_bucket(data.get("stackables") or {}, stack_count))

        return self._merge_stat_buckets(*buckets)

    def _prepare_upgrade_payload_from_bucket(self, bucket_data: dict[str, Any], *, section: str | None = None) -> dict[str, Any]:
        source = deepcopy(bucket_data or {})
        payload: dict[str, Any] = {}
        damage_values: dict[str, Any] = {}

        for key, value in source.items():
            stat_key = normalized_slug(key)

            if stat_key in DAMAGE_TYPES:
                damage_values[stat_key] = value
            else:
                payload[stat_key] = value

        payload["damage_dist"] = self._make_dist_object(damage_values)

        if section == "mods":
            payload.setdefault("category", "mod")
        elif section == "arcanes":
            payload.setdefault("category", "arcane")

        return payload

    def _prepare_upgrade_payload(self, data: dict[str, Any], *, section: str | None = None, stacks: int | None = None, condition: bool = True) -> dict[str, Any]:
        bucket = self._effective_upgrade_bucket(data, stacks=stacks, condition=condition)
        return self._prepare_upgrade_payload_from_bucket(bucket, section=section)

    def _make_weapon_object(self, section: str, name: str, data: dict[str, Any]) -> Primary | Secondary | Melee:
        payload = self._prepare_weapon_payload(section, name, data)
        return self._construct_object(self._weapon_model_class(section), name, payload)

    def _make_upgrade_object(self, name: str, data: dict[str, Any], *, section: str | None = None, stacks: int | None = None, condition: bool = True) -> Upgrade:
        payload = self._prepare_upgrade_payload(data, section=section, stacks=stacks, condition=condition)
        return self._construct_object(Upgrade, name, payload)

    def _make_upgrade_bucket_object(self, name: str, data: dict[str, Any], *, section: str | None = None, bucket: str = "stats", stacks: int | None = None) -> Upgrade:
        raw_bucket = deepcopy(data.get(bucket) or {})

        if bucket == "stackables":
            scale = 1 if stacks is None else self._resolve_stack_count(data, stacks)
            raw_bucket = self._scale_stat_bucket(raw_bucket, scale)

        payload = self._prepare_upgrade_payload_from_bucket(raw_bucket, section=section)
        return self._construct_object(Upgrade, name, payload)

    def _construct_object(self, cls: type, name: str, data: dict[str, Any]) -> Any:
        payload = deepcopy(data)

        attempts = []

        if "name" in payload:
            attempts.extend([
                lambda: cls(**payload),
                lambda: cls(payload),
                lambda: cls(name, payload),
            ])
        else:
            attempts.extend([
                lambda: cls(name=name, **payload),
                lambda: cls(**payload),
                lambda: cls(name, **payload),
                lambda: cls(payload),
                lambda: cls(name, payload),
            ])

        for attempt in attempts:
            try:
                return attempt()
            except TypeError:
                pass

        try:
            sig = signature(cls)
            params = sig.parameters
            accepts_var_kwargs = any(p.kind == Parameter.VAR_KEYWORD for p in params.values())

            if accepts_var_kwargs:
                if "name" not in payload:
                    payload["name"] = name
                return cls(**payload)

            filtered = {
                key: value
                for key, value in payload.items()
                if key in params
            }

            if "name" in params:
                filtered.setdefault("name", name)

            return cls(**filtered)

        except Exception as exc:
            raise TypeError(
                f"Could not construct {cls.__name__} object for {name!r}. "
                f"Check that the JSON keys match the {cls.__name__} constructor."
            ) from exc


