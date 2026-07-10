from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from ..models import Upgrade, Primary, Secondary, Melee
from .normalization import normalized_key
from .records import MatchResult


class DatabaseAccessMixin:
    def get_weapon(self, name: str, *, include_section: bool = False) -> Primary | Secondary | Melee | MatchResult | None:
        found = self._weapon_index.get(normalized_key(name))
        if not found:
            return None

        section, real_name = found
        obj = self._make_weapon_object(section, real_name, self.weapons[section][real_name])

        if include_section:
            return MatchResult(section=section, name=real_name, data=obj)
        return obj

    def get_upgrade(self, name: str, *, stacks: int | None = None, condition: bool = True, include_section: bool = False) -> Upgrade | MatchResult | None:
        found = self._upgrade_index.get(normalized_key(name))
        if not found:
            return None

        section, real_name = found
        obj = self._make_upgrade_object(real_name, self.upgrades[section][real_name], section=section, stacks=stacks, condition=condition)

        if include_section:
            return MatchResult(section=section, name=real_name, data=obj)
        return obj

    def get_conditional_upgrade(self, name: str, *, include_section: bool = False) -> Upgrade | MatchResult | None:
        found = self._upgrade_index.get(normalized_key(name))
        if not found:
            return None

        section, real_name = found
        obj = self._make_upgrade_bucket_object(real_name, self.upgrades[section][real_name], section=section, bucket="conditionals")
        
        if include_section:
            return MatchResult(section=section, name=real_name, data=obj)
        return obj

    def get_stackable_upgrade(self, name: str, *, stacks: int | None = None, include_section: bool = False) -> Upgrade | MatchResult | None:
        """Return only the stackables bucket as an Upgrade object; default is per-stack value."""
        found = self._upgrade_index.get(normalized_key(name))
        if not found:
            return None

        section, real_name = found
        obj = self._make_upgrade_bucket_object(real_name, self.upgrades[section][real_name], section=section, bucket="stackables", stacks=stacks)

        if include_section:
            return MatchResult(section=section, name=real_name, data=obj)
        return obj

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

    def filter_weapons(self, weapon_type: str | Iterable[str] | None = None, *, include_sections: bool = False) -> dict[str, Primary | Secondary | Melee] | dict[str, dict[str, Primary | Secondary | Melee]]:
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

    def filter_raw_weapons(self, weapon_type: str | Iterable[str] | None = None, *, include_sections: bool = False) -> dict[str, Any] | dict[str, dict[str, Any]]:
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

    def filter_upgrades(self, weapon_type: str | Iterable[str] | None = None, *, stacks: int | None = None, condition: bool = True, include_mods: bool = True, include_arcanes: bool = True, include_sections: bool = False) -> dict[str, Upgrade] | dict[str, dict[str, Upgrade]]:
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
                    obj = self._make_upgrade_object(name, upgrade, section=section, stacks=stacks, condition=condition)
                    if include_sections:
                        result.setdefault(section, {})[name] = obj
                    else:
                        result[name] = obj

        return result

    def filter_upgrades_for_weapon(self, weapon_name: str, *, stacks: int | None = None, condition: bool = True, include_mods: bool = True, include_arcanes: bool = True, include_sections: bool = False) -> dict[str, Upgrade] | dict[str, dict[str, Upgrade]]:
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

    def filter_conditional_upgrades_for_weapon(self, weapon_name: str, *, include_mods: bool = True, include_arcanes: bool = True, include_sections: bool = False) -> dict[str, Upgrade] | dict[str, dict[str, Upgrade]]:
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
                    obj = self._make_upgrade_bucket_object(upgrade_name, upgrade, section=section, bucket="conditionals")
                    if include_sections:
                        result.setdefault(section, {})[upgrade_name] = obj
                    else:
                        result[upgrade_name] = obj

        return result

    def filter_stackable_upgrades_for_weapon(self, weapon_name: str, *, stacks: int | None = None, include_mods: bool = True, include_arcanes: bool = True, include_sections: bool = False) -> dict[str, Upgrade] | dict[str, dict[str, Upgrade]]:
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
                    obj = self._make_upgrade_bucket_object(upgrade_name, upgrade, section=section, bucket="stackables", stacks=stacks)
                    if include_sections:
                        result.setdefault(section, {})[upgrade_name] = obj
                    else:
                        result[upgrade_name] = obj

        return result

    def upgrade_names(self, weapon_type: str | Iterable[str] | None = None) -> list[str]:
        return sorted(self.filter_raw_upgrades(weapon_type).keys(), key=normalized_key)

    def upgrade_names_for_weapon(self, weapon_name: str) -> list[str]:
        return sorted(self.filter_raw_upgrades_for_weapon(weapon_name).keys(), key=normalized_key)

    def filter_raw_upgrades(self, weapon_type: str | Iterable[str] | None = None, *, include_mods: bool = True, include_arcanes: bool = True, include_sections: bool = False) -> dict[str, Any] | dict[str, dict[str, Any]]:
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

    def filter_raw_upgrades_for_weapon(self, weapon_name: str, *, include_mods: bool = True, include_arcanes: bool = True, include_sections: bool = False) -> dict[str, Any] | dict[str, dict[str, Any]]:
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


