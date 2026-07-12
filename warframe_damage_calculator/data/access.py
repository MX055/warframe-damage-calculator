from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable

from ..models import Melee, Primary, Secondary, Upgrade, dist
from .normalization import as_list, normalized_key, normalized_slug


Weapon = Primary | Secondary | Melee
ArsenalItem = Weapon | Upgrade
ArsenalValue = ArsenalItem | str | float | int | bool | dist


class DatabaseAccessMixin:
    def _find_weapon(self, name: str) -> tuple[str, str] | None:
        return self._weapon_index.get(normalized_key(name))

    def _find_upgrade(self, name: str) -> tuple[str, str] | None:
        return self._upgrade_index.get(normalized_key(name))

    def _normalized_filter(self, value: str | None) -> str | None:
        if value is None:
            return None

        key = normalized_slug(value)
        aliases = {"weapons": "weapon", "primaries": "primary", "secondaries": "secondary", "pistol": "secondary", "pistols": "secondary", "melees": "melee", "upgrades": "upgrade", "mods": "mod", "arcanes": "arcane"}
        return aliases.get(key, key)

    def _type_filter_set(self, value: str | None) -> set[str]:
        if value is None:
            return set()
        return self._expanded_type_filter(value)

    def _value_matches_requested(self, value: Any, requested: set[str]) -> bool:
        return bool({normalized_slug(item) for item in as_list(value)} & requested)

    def _requirements_match_type(self, requirements: dict[str, Any], requested: set[str]) -> bool:
        for key, value in (requirements or {}).items():
            if normalized_slug(key) in requested:
                return True
            if self._value_matches_requested(value, requested):
                return True
        return False

    def _weapon_matches_filter(self, section: str, data: dict[str, Any], type: str | None) -> bool:
        type = self._normalized_filter(type)
        requested = self._type_filter_set(type)

        if type is None or type == "weapon":
            return True
        if type in {"mod", "arcane", "upgrade"}:
            return False

        if type == "primary":
            return section == "primaries"
        if type == "secondary":
            return section == "secondaries"
        if type == "melee":
            return section == "melees"

        return self._weapon_matches_type(section, data, requested) or self._value_matches_requested(data.get("type"), requested) or self._value_matches_requested(data.get("trigger"), requested)

    def _upgrade_matches_filter(self, section: str, data: dict[str, Any], type: str | None) -> bool:
        type = self._normalized_filter(type)
        requested = self._type_filter_set(type)

        if type is None or type == "upgrade":
            return True
        if type == "mod":
            return section == "mods"
        if type == "arcane":
            return section == "arcanes"
        if type == "weapon":
            return False

        return self._upgrade_matches_type(data, requested) or self._requirements_match_type(data.get("requirements") or {}, requested)

    def _rank_multiplier(self, data: dict[str, Any], rank: int | None) -> float:
        if rank is None:
            return 1.0

        max_rank = data.get("max_rank")
        if max_rank is None:
            max_rank = data.get("rank")

        try:
            max_rank = int(max_rank)
        except (TypeError, ValueError):
            return 1.0

        if max_rank <= 0:
            return 1.0

        rank = max(0, min(int(rank), max_rank))
        return (rank + 1) / (max_rank + 1)

    def _scale_upgrade_for_rank(self, upgrade: Upgrade, data: dict[str, Any], rank: int | None) -> Upgrade:
        multiplier = self._rank_multiplier(data, rank)
        if multiplier == 1:
            return upgrade

        def scale(value: Any) -> Any:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float, dist)):
                return value * multiplier
            return value

        return replace(
            upgrade,
            stats={key: scale(value) for key, value in upgrade.stats.items()},
            conditional_stats={key: (scale(value), condition) for key, (value, condition) in upgrade.conditional_stats.items()},
            stacking_stats={key: (scale(value), condition) for key, (value, condition) in upgrade.stacking_stats.items()},
        )

    def _make_matching_weapon(self, name: str, *, type: str | None) -> Weapon | None:
        found = self._find_weapon(name)
        if found is None:
            return None

        section, real_name = found
        data = self.weapons[section][real_name]

        if not self._weapon_matches_filter(section, data, type):
            return None

        return self._make_weapon_object(section, real_name, data)

    def _make_matching_upgrade(self, name: str, *, type: str | None, rank: int | None) -> Upgrade | None:
        found = self._find_upgrade(name)
        if found is None:
            return None

        section, real_name = found
        data = self.upgrades[section][real_name]

        if not self._upgrade_matches_filter(section, data, type):
            return None

        upgrade = self._make_upgrade_object(real_name, data, section=section)
        return self._scale_upgrade_for_rank(upgrade, data, rank)

    def _iter_matching_items(self, *, type: str | None, rank: int | None) -> Iterable[tuple[str, ArsenalItem]]:
        for section, entries in self.weapons.items():
            for name, data in entries.items():
                if self._weapon_matches_filter(section, data, type):
                    yield name, self._make_weapon_object(section, name, data)

        for section, entries in self.upgrades.items():
            for name, data in entries.items():
                if self._upgrade_matches_filter(section, data, type):
                    upgrade = self._make_upgrade_object(name, data, section=section)
                    yield name, self._scale_upgrade_for_rank(upgrade, data, rank)

    def _extract_attribute(self, item: ArsenalItem, attribute: str) -> ArsenalValue | None:
        attr = normalized_slug(attribute)

        if attr == "name":
            if isinstance(item, Upgrade):
                return item.name
            return getattr(item.stats.base, "name", None)

        if hasattr(item, attr):
            return getattr(item, attr)

        if hasattr(item, "stats"):
            for source_name in ("base", "effective"):
                source = getattr(item.stats, source_name, None)
                if source is not None and hasattr(source, attr):
                    return getattr(source, attr)

            if hasattr(item.stats, attr):
                return getattr(item.stats, attr)

        return None

    def _apply_attribute(self, item: ArsenalItem, attribute: str | None) -> ArsenalItem | ArsenalValue | None:
        if attribute is None:
            return item
        return self._extract_attribute(item, attribute)

    def get(self, name: str | None = None, *, type: str | None = None, rank: int | None = None, atribute: str | None = None) -> ArsenalItem | ArsenalValue | dict[str, ArsenalItem | ArsenalValue | None] | list[str] | None:
        if name is not None:
            matches: list[ArsenalItem] = []

            weapon = self._make_matching_weapon(name, type=type)
            if weapon is not None:
                matches.append(weapon)

            upgrade = self._make_matching_upgrade(name, type=type, rank=rank)
            if upgrade is not None:
                matches.append(upgrade)

            if not matches:
                return None

            if len(matches) > 1:
                raise ValueError(f"Ambiguous arsenal item name {name!r}. Pass a more specific type, such as type='primary', type='mod', or type='arcane'.")

            return self._apply_attribute(matches[0], atribute)

        items = dict(sorted(self._iter_matching_items(type=type, rank=rank), key=lambda item: normalized_key(item[0])))

        if atribute is None:
            return items

        if normalized_slug(atribute) == "name":
            return list(items.keys())

        return {item_name: self._extract_attribute(item, atribute) for item_name, item in items.items()}
