"""
Loader for the reformatted Warframe damage calculator database.

Expected files:
    weapons.json
    upgrades.json

Expected weapon sections:
    primaries
    secondaries
    melees

Expected upgrade sections:
    mods
    arcanes

Public methods return calculator model objects:
    - Primary
    - Secondary
    - Melee
    - Upgrade

Raw dict access is still available through get_raw_weapon(), get_raw_upgrade(),
filter_raw_weapons(), and filter_raw_upgrades().

Important conversion behavior:
    - Weapon damage_dist / forced_procs / explosion_damage_dist /
      explosion_forced_procs dictionaries are converted into dist objects.
    - Upgrade elemental/physical stat keys such as heat, toxin, impact, slash,
      etc. are moved into Upgrade.damage_dist before construction.
    - Upgrade objects are effective upgrades:
        stats
        + conditionals if condition=True
        + stackables * stacks
      where stacks defaults to the upgrade's max_stacks.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from inspect import Parameter, signature
from pathlib import Path
from typing import Any, Iterable
import json
import re

from ..models import Upgrade, Primary, Secondary, Melee, dist


DAMAGE_TYPES = {
    "impact",
    "puncture",
    "slash",
    "blast",
    "corrosive",
    "gas",
    "magnetic",
    "radiation",
    "viral",
    "cold",
    "electricity",
    "heat",
    "toxin",
}

WEAPON_DIST_FIELDS = (
    "damage_dist",
    "forced_procs",
    "explosion_damage_dist",
    "explosion_forced_procs",
)

PRIMARY_TYPES = {"primary", "rifle", "bow", "shotgun", "sniper"}
SECONDARY_TYPES = {"secondary", "pistol"}
MELEE_TYPES = {"melee"}

TYPE_ALIASES = {
    "primary": {"primary", "rifle", "bow", "shotgun", "sniper"},
    "primaries": {"primary", "rifle", "bow", "shotgun", "sniper"},
    "secondary": {"pistol"},
    "secondaries": {"pistol"},
    "pistol": {"pistol"},
    "melee": {"melee"},
    "melees": {"melee"},
}


def normalized_key(value: Any) -> str:
    """Normalize names/types for lookup without changing stored database values."""
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def normalized_slug(value: Any) -> str:
    """Normalize compatibility/type strings like 'Semi Rifle' -> 'semi_rifle'."""
    return re.sub(r"[^a-z0-9]+", "_", normalized_key(value)).strip("_")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


@dataclass(frozen=True)
class MatchResult:
    section: str
    name: str
    data: Any


class WarframeDatabase:
    def __init__(self, weapons: dict[str, Any], upgrades: dict[str, Any]) -> None:
        self.weapons = weapons
        self.upgrades = upgrades

        self._weapon_index: dict[str, tuple[str, str]] = {}
        self._upgrade_index: dict[str, tuple[str, str]] = {}

        for section, entries in self.weapons.items():
            for name in entries:
                self._weapon_index[normalized_key(name)] = (section, name)

        for section, entries in self.upgrades.items():
            for name in entries:
                self._upgrade_index[normalized_key(name)] = (section, name)

    @classmethod
    def from_files(
        cls,
        weapons_path: str | Path = "weapons.json",
        upgrades_path: str | Path = "upgrades.json",
    ) -> "WarframeDatabase":
        return cls(load_json(weapons_path), load_json(upgrades_path))

    @classmethod
    def from_folder(cls, folder: str | Path) -> "WarframeDatabase":
        folder = Path(folder)
        return cls.from_files(folder / "weapons.json", folder / "upgrades.json")

    # ----------------------------
    # Object construction
    # ----------------------------

    def _weapon_model_class(self, section: str) -> type:
        if section == "primaries":
            return Primary
        if section == "secondaries":
            return Secondary
        if section == "melees":
            return Melee
        raise ValueError(f"Unknown weapon section: {section!r}")

    def _make_dist_object(self, values: dict[str, Any] | None) -> dist:
        """
        Convert a JSON damage/proc dictionary into your dist model.

        The normal expected constructor is:
            dist(impact=..., slash=..., heat=...)

        The fallback branches make this tolerant if your dist class changes later.
        """
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
                # If dist is immutable or does not expose that field, ignore here;
                # the constructor error above would have caught the normal case.
                pass
        return obj

    def _prepare_weapon_payload(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        """Convert weapon dist dictionaries into dist objects before model construction."""
        payload = deepcopy(data)

        # Weapon JSON entries are indexed by name, but the model classes may also
        # have a real name attribute. Add it here so Primary/Secondary/Melee
        # constructors receive it.
        payload.setdefault("name", name)

        for field_name in WEAPON_DIST_FIELDS:
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
        """Scale numeric stackable stats while leaving bool/non-numeric values safe."""
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
        """Merge stat dictionaries, summing numeric duplicates."""
        merged: dict[str, Any] = {}

        for bucket in buckets:
            for key, value in (bucket or {}).items():
                if isinstance(value, bool):
                    # Locks are effectively on/off flags.
                    merged[key] = bool(merged.get(key, False)) or value
                elif isinstance(value, int | float) and isinstance(merged.get(key), int | float) and not isinstance(merged.get(key), bool):
                    merged[key] += value
                else:
                    merged[key] = value

        return merged

    def _effective_upgrade_bucket(
        self,
        data: dict[str, Any],
        *,
        stacks: int | None,
        condition: bool,
    ) -> dict[str, Any]:
        """
        Return the effective stat bucket used to build an Upgrade object.

        stats are always included.
        conditionals are included when condition=True.
        stackables are included as stackables * stacks, with stacks defaulting
        to max_stacks.
        """
        stack_count = self._resolve_stack_count(data, stacks)

        buckets: list[dict[str, Any]] = [
            deepcopy(data.get("stats") or {}),
        ]

        if condition:
            buckets.append(deepcopy(data.get("conditionals") or {}))

        if stack_count:
            buckets.append(self._scale_stat_bucket(data.get("stackables") or {}, stack_count))

        return self._merge_stat_buckets(*buckets)

    def _prepare_upgrade_payload_from_bucket(
        self,
        bucket_data: dict[str, Any],
        *,
        section: str | None = None,
    ) -> dict[str, Any]:
        """
        Convert one flat stat bucket into an Upgrade constructor payload.

        Elemental/physical keys are moved into damage_dist.
        Other calculator keys are passed normally.
        """
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

    def _prepare_upgrade_payload(
        self,
        data: dict[str, Any],
        *,
        section: str | None = None,
        stacks: int | None = None,
        condition: bool = True,
    ) -> dict[str, Any]:
        """Convert an upgrade database entry into an effective Upgrade payload."""
        bucket = self._effective_upgrade_bucket(data, stacks=stacks, condition=condition)
        return self._prepare_upgrade_payload_from_bucket(bucket, section=section)

    def _make_weapon_object(self, section: str, name: str, data: dict[str, Any]) -> Primary | Secondary | Melee:
        payload = self._prepare_weapon_payload(name, data)
        return self._construct_object(self._weapon_model_class(section), name, payload)

    def _make_upgrade_object(
        self,
        name: str,
        data: dict[str, Any],
        *,
        section: str | None = None,
        stacks: int | None = None,
        condition: bool = True,
    ) -> Upgrade:
        payload = self._prepare_upgrade_payload(data, section=section, stacks=stacks, condition=condition)
        return self._construct_object(Upgrade, name, payload)

    def _make_upgrade_bucket_object(
        self,
        name: str,
        data: dict[str, Any],
        *,
        section: str | None = None,
        bucket: str = "stats",
        stacks: int | None = None,
    ) -> Upgrade:
        """
        Build only one raw bucket as an Upgrade object.

        For bucket="stackables", stacks defaults to 1 because this method is
        meant to expose the per-stack value. Pass stacks=n to scale it.
        """
        raw_bucket = deepcopy(data.get(bucket) or {})

        if bucket == "stackables":
            scale = 1 if stacks is None else self._resolve_stack_count(data, stacks)
            raw_bucket = self._scale_stat_bucket(raw_bucket, scale)

        payload = self._prepare_upgrade_payload_from_bucket(raw_bucket, section=section)
        return self._construct_object(Upgrade, name, payload)

    def _construct_object(self, cls: type, name: str, data: dict[str, Any]) -> Any:
        """
        Construct a model object without hard-coding the exact constructor style.

        It supports common patterns:
            Class(name="Serration", **data)
            Class(**data)
            Class("Serration", **data)
            Class(data)
            Class(name="Serration", **filtered_data)

        This makes the loader work even if your model dataclasses/classes differ
        slightly in whether they store the name field.
        """
        payload = deepcopy(data)

        attempts = []

        if "name" in payload:
            # If the payload already has a name field, do not also pass
            # name=name or Python will raise "multiple values for argument".
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

        # Last attempt: inspect the constructor and pass only accepted kwargs.
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

    # ----------------------------
    # Direct name lookup: objects
    # ----------------------------

    def get_weapon(self, name: str, *, include_section: bool = False) -> Primary | Secondary | Melee | MatchResult | None:
        found = self._weapon_index.get(normalized_key(name))
        if not found:
            return None

        section, real_name = found
        obj = self._make_weapon_object(section, real_name, self.weapons[section][real_name])

        if include_section:
            return MatchResult(section=section, name=real_name, data=obj)
        return obj

    def get_upgrade(
        self,
        name: str,
        *,
        stacks: int | None = None,
        condition: bool = True,
        include_section: bool = False,
    ) -> Upgrade | MatchResult | None:
        """
        Return an effective Upgrade object.

        stacks:
            Number of stackable stacks to apply.
            Defaults to the upgrade's max_stacks.
            Use stacks=0 to ignore stackables.

        condition:
            Whether conditionals should be applied.
            Defaults to True.
            Use condition=False to load only always-on stats + stackables.
        """
        found = self._upgrade_index.get(normalized_key(name))
        if not found:
            return None

        section, real_name = found
        obj = self._make_upgrade_object(
            real_name,
            self.upgrades[section][real_name],
            section=section,
            stacks=stacks,
            condition=condition,
        )

        if include_section:
            return MatchResult(section=section, name=real_name, data=obj)
        return obj

    def get_conditional_upgrade(self, name: str, *, include_section: bool = False) -> Upgrade | MatchResult | None:
        """Return only the conditionals bucket as an Upgrade object."""
        found = self._upgrade_index.get(normalized_key(name))
        if not found:
            return None

        section, real_name = found
        obj = self._make_upgrade_bucket_object(
            real_name,
            self.upgrades[section][real_name],
            section=section,
            bucket="conditionals",
        )

        if include_section:
            return MatchResult(section=section, name=real_name, data=obj)
        return obj

    def get_stackable_upgrade(
        self,
        name: str,
        *,
        stacks: int | None = None,
        include_section: bool = False,
    ) -> Upgrade | MatchResult | None:
        """Return only the stackables bucket as an Upgrade object; default is per-stack value."""
        found = self._upgrade_index.get(normalized_key(name))
        if not found:
            return None

        section, real_name = found
        obj = self._make_upgrade_bucket_object(
            real_name,
            self.upgrades[section][real_name],
            section=section,
            bucket="stackables",
            stacks=stacks,
        )

        if include_section:
            return MatchResult(section=section, name=real_name, data=obj)
        return obj

    # ----------------------------
    # Direct name lookup: raw dicts
    # ----------------------------

    def get_raw_weapon(self, name: str, *, include_section: bool = False) -> dict[str, Any] | MatchResult | None:
        found = self._weapon_index.get(normalized_key(name))
        if not found:
            return None

        section, real_name = found
        data = deepcopy(self.weapons[section][real_name])

        if include_section:
            return MatchResult(section=section, name=real_name, data=data)
        return data

    def get_raw_upgrade(self, name: str, *, include_section: bool = False) -> dict[str, Any] | MatchResult | None:
        found = self._upgrade_index.get(normalized_key(name))
        if not found:
            return None

        section, real_name = found
        data = deepcopy(self.upgrades[section][real_name])

        if include_section:
            return MatchResult(section=section, name=real_name, data=data)
        return data

    # ----------------------------
    # Weapon filtering: objects
    # ----------------------------

    def filter_weapons(
        self,
        weapon_type: str | Iterable[str] | None = None,
        *,
        include_sections: bool = False,
    ) -> dict[str, Primary | Secondary | Melee] | dict[str, dict[str, Primary | Secondary | Melee]]:
        """
        Filter weapons by section or concrete weapon type.

        Examples:
            filter_weapons("primary")   -> dict[str, Primary]
            filter_weapons("secondary") -> dict[str, Secondary]
            filter_weapons("melee")     -> dict[str, Melee]
            filter_weapons("rifle")     -> primary weapons with type == rifle
            filter_weapons("nikana")    -> melee weapons with type == nikana
        """
        requested = self._expanded_type_filter(weapon_type)
        result: dict[str, Any] = {}

        for section, entries in self.weapons.items():
            for name, weapon in entries.items():
                if self._weapon_matches_type(section, weapon, requested):
                    obj = self._make_weapon_object(section, name, weapon)
                    if include_sections:
                        result.setdefault(section, {})[name] = obj
                    else:
                        result[name] = obj

        return result

    def weapon_names(self, weapon_type: str | Iterable[str] | None = None) -> list[str]:
        return sorted(self.filter_raw_weapons(weapon_type).keys(), key=normalized_key)

    # ----------------------------
    # Weapon filtering: raw dicts
    # ----------------------------

    def filter_raw_weapons(
        self,
        weapon_type: str | Iterable[str] | None = None,
        *,
        include_sections: bool = False,
    ) -> dict[str, Any] | dict[str, dict[str, Any]]:
        requested = self._expanded_type_filter(weapon_type)
        result: dict[str, Any] = {}

        for section, entries in self.weapons.items():
            for name, weapon in entries.items():
                if self._weapon_matches_type(section, weapon, requested):
                    if include_sections:
                        result.setdefault(section, {})[name] = deepcopy(weapon)
                    else:
                        result[name] = deepcopy(weapon)

        return result

    # ----------------------------
    # Upgrade filtering: objects
    # ----------------------------

    def filter_upgrades(
        self,
        weapon_type: str | Iterable[str] | None = None,
        *,
        stacks: int | None = None,
        condition: bool = True,
        include_mods: bool = True,
        include_arcanes: bool = True,
        include_sections: bool = False,
    ) -> dict[str, Upgrade] | dict[str, dict[str, Upgrade]]:
        """
        Filter effective upgrades by broad compatibility.

        stacks and condition behave the same as get_upgrade().
        """
        requested = self._expanded_type_filter(weapon_type)

        allowed_sections = set()
        if include_mods:
            allowed_sections.add("mods")
        if include_arcanes:
            allowed_sections.add("arcanes")

        result: dict[str, Any] = {}

        for section, entries in self.upgrades.items():
            if section not in allowed_sections:
                continue

            for name, upgrade in entries.items():
                if self._upgrade_matches_type(upgrade, requested):
                    obj = self._make_upgrade_object(
                        name,
                        upgrade,
                        section=section,
                        stacks=stacks,
                        condition=condition,
                    )
                    if include_sections:
                        result.setdefault(section, {})[name] = obj
                    else:
                        result[name] = obj

        return result

    def filter_upgrades_for_weapon(
        self,
        weapon_name: str,
        *,
        stacks: int | None = None,
        condition: bool = True,
        include_mods: bool = True,
        include_arcanes: bool = True,
        include_sections: bool = False,
    ) -> dict[str, Upgrade] | dict[str, dict[str, Upgrade]]:
        """
        Filter effective upgrades that can apply to a specific weapon.

        This checks:
            - exact weapon-name compatibility, e.g. ["sobek"]
            - weapon type compatibility, e.g. ["rifle", "bow"]
            - broad family compatibility, e.g. ["primary"]
            - requirements, e.g. {"trigger": ["semi"]}, {"is_beam": true}

        stacks and condition behave the same as get_upgrade().
        """
        found = self.get_raw_weapon(weapon_name, include_section=True)
        if found is None:
            return {}

        assert isinstance(found, MatchResult)
        weapon = found.data
        real_weapon_name = found.name

        allowed_sections = set()
        if include_mods:
            allowed_sections.add("mods")
        if include_arcanes:
            allowed_sections.add("arcanes")

        result: dict[str, Any] = {}

        for section, entries in self.upgrades.items():
            if section not in allowed_sections:
                continue

            for upgrade_name, upgrade in entries.items():
                if self._upgrade_matches_weapon(upgrade, real_weapon_name, weapon, found.section):
                    obj = self._make_upgrade_object(
                        upgrade_name,
                        upgrade,
                        section=section,
                        stacks=stacks,
                        condition=condition,
                    )
                    if include_sections:
                        result.setdefault(section, {})[upgrade_name] = obj
                    else:
                        result[upgrade_name] = obj

        return result

    def filter_conditional_upgrades_for_weapon(
        self,
        weapon_name: str,
        *,
        include_mods: bool = True,
        include_arcanes: bool = True,
        include_sections: bool = False,
    ) -> dict[str, Upgrade] | dict[str, dict[str, Upgrade]]:
        """Return only conditional buckets for upgrades that match a weapon."""
        found = self.get_raw_weapon(weapon_name, include_section=True)
        if found is None:
            return {}

        assert isinstance(found, MatchResult)
        weapon = found.data
        real_weapon_name = found.name

        allowed_sections = set()
        if include_mods:
            allowed_sections.add("mods")
        if include_arcanes:
            allowed_sections.add("arcanes")

        result: dict[str, Any] = {}

        for section, entries in self.upgrades.items():
            if section not in allowed_sections:
                continue

            for upgrade_name, upgrade in entries.items():
                if self._upgrade_matches_weapon(upgrade, real_weapon_name, weapon, found.section):
                    obj = self._make_upgrade_bucket_object(
                        upgrade_name,
                        upgrade,
                        section=section,
                        bucket="conditionals",
                    )
                    if include_sections:
                        result.setdefault(section, {})[upgrade_name] = obj
                    else:
                        result[upgrade_name] = obj

        return result

    def filter_stackable_upgrades_for_weapon(
        self,
        weapon_name: str,
        *,
        stacks: int | None = None,
        include_mods: bool = True,
        include_arcanes: bool = True,
        include_sections: bool = False,
    ) -> dict[str, Upgrade] | dict[str, dict[str, Upgrade]]:
        """Return only stackable buckets for upgrades that match a weapon."""
        found = self.get_raw_weapon(weapon_name, include_section=True)
        if found is None:
            return {}

        assert isinstance(found, MatchResult)
        weapon = found.data
        real_weapon_name = found.name

        allowed_sections = set()
        if include_mods:
            allowed_sections.add("mods")
        if include_arcanes:
            allowed_sections.add("arcanes")

        result: dict[str, Any] = {}

        for section, entries in self.upgrades.items():
            if section not in allowed_sections:
                continue

            for upgrade_name, upgrade in entries.items():
                if self._upgrade_matches_weapon(upgrade, real_weapon_name, weapon, found.section):
                    obj = self._make_upgrade_bucket_object(
                        upgrade_name,
                        upgrade,
                        section=section,
                        bucket="stackables",
                        stacks=stacks,
                    )
                    if include_sections:
                        result.setdefault(section, {})[upgrade_name] = obj
                    else:
                        result[upgrade_name] = obj

        return result

    def upgrade_names(self, weapon_type: str | Iterable[str] | None = None) -> list[str]:
        return sorted(self.filter_raw_upgrades(weapon_type).keys(), key=normalized_key)

    def upgrade_names_for_weapon(self, weapon_name: str) -> list[str]:
        return sorted(self.filter_raw_upgrades_for_weapon(weapon_name).keys(), key=normalized_key)

    # ----------------------------
    # Upgrade filtering: raw dicts
    # ----------------------------

    def filter_raw_upgrades(
        self,
        weapon_type: str | Iterable[str] | None = None,
        *,
        include_mods: bool = True,
        include_arcanes: bool = True,
        include_sections: bool = False,
    ) -> dict[str, Any] | dict[str, dict[str, Any]]:
        requested = self._expanded_type_filter(weapon_type)

        allowed_sections = set()
        if include_mods:
            allowed_sections.add("mods")
        if include_arcanes:
            allowed_sections.add("arcanes")

        result: dict[str, Any] = {}

        for section, entries in self.upgrades.items():
            if section not in allowed_sections:
                continue

            for name, upgrade in entries.items():
                if self._upgrade_matches_type(upgrade, requested):
                    if include_sections:
                        result.setdefault(section, {})[name] = deepcopy(upgrade)
                    else:
                        result[name] = deepcopy(upgrade)

        return result

    def filter_raw_upgrades_for_weapon(
        self,
        weapon_name: str,
        *,
        include_mods: bool = True,
        include_arcanes: bool = True,
        include_sections: bool = False,
    ) -> dict[str, Any] | dict[str, dict[str, Any]]:
        found = self.get_raw_weapon(weapon_name, include_section=True)
        if found is None:
            return {}

        assert isinstance(found, MatchResult)
        weapon = found.data
        real_weapon_name = found.name

        allowed_sections = set()
        if include_mods:
            allowed_sections.add("mods")
        if include_arcanes:
            allowed_sections.add("arcanes")

        result: dict[str, Any] = {}

        for section, entries in self.upgrades.items():
            if section not in allowed_sections:
                continue

            for upgrade_name, upgrade in entries.items():
                if self._upgrade_matches_weapon(upgrade, real_weapon_name, weapon, found.section):
                    if include_sections:
                        result.setdefault(section, {})[upgrade_name] = deepcopy(upgrade)
                    else:
                        result[upgrade_name] = deepcopy(upgrade)

        return result

    # ----------------------------
    # Matching helpers
    # ----------------------------

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

        # "secondary" is accepted as a query alias, even if the database stores
        # secondary upgrades as pistol-compatible instead of using a "secondary" tag.
        if "pistol" in requested and "pistol" in compatibility:
            return True

        # "primary" should match upgrades compatible with any primary subtype.
        if "primary" in requested and compatibility & PRIMARY_TYPES:
            return True

        return bool(compatibility & requested)

    def _upgrade_matches_weapon(
        self,
        upgrade: dict[str, Any],
        weapon_name: str,
        weapon: dict[str, Any],
        weapon_section: str,
    ) -> bool:
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

        compatible = (
            weapon_name_key in compatibility
            or weapon_type in compatibility
            or weapon_family in compatibility
        )

        if not compatible:
            return False

        return self._requirements_match(weapon, upgrade.get("requirements") or {})

    def _requirements_match(self, weapon: dict[str, Any], requirements: dict[str, Any]) -> bool:
        """
        Generic requirement matcher.

        Supported exact fields:
            trigger, type, is_beam, is_battery

        Also supports future numeric bounds:
            min_burst_count, max_burst_count
            min_charge_time, max_charge_time
            etc.
        """
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
                # Future-proof fallback:
                # if the weapon has the field, require equality;
                # if it does not, fail closed so restrictions are not ignored.
                if key not in weapon:
                    return False
                if weapon.get(key) != expected:
                    return False

        return True


db = WarframeDatabase.from_files("weapons.json", "upgrades.json")
