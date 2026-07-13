from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal, overload

from ..models import Upgrade
from ..models.dist import dist
from .construction import ArsenalItem, DatabaseFactory
from .matching import entry_matches
from .normalization import normalize_identifier, normalize_name
from .paths import DEFAULT_UPGRADES_PATH, DEFAULT_WEAPONS_PATH, load_json
from .schema import DatabaseEntry, DatabaseRecords, ItemCategory


ArsenalValue = (
    ArsenalItem
    | str
    | float
    | int
    | bool
    | dist
    | tuple[Any, str]
    | set[str]
    | dict[str, Any]
)

_SECTION_ALIASES: dict[str, ItemCategory] = {
    "primary": "primary",
    "primaries": "primary",
    "secondary": "secondary",
    "secondaries": "secondary",
    "melee": "melee",
    "melees": "melee",
    "mod": "mod",
    "mods": "mod",
    "arcane": "arcane",
    "arcanes": "arcane",
}

_ATTRIBUTE_ALIASES = {
    "damage": "damage_dist",
    "explosion_damage": "explosion_damage_dist",
}


class WarframeDatabase:
    def __init__(self, weapons: Mapping[str, Any], upgrades: Mapping[str, Any]) -> None:
        self.weapons = self._normalize_sections(weapons, {"primary", "secondary", "melee"})
        self.upgrades = self._normalize_sections(upgrades, {"mod", "arcane"})
        self._factory = DatabaseFactory()
        self._entries = tuple(self._iter_database_entries())

        index: dict[str, list[DatabaseEntry]] = defaultdict(list)
        for entry in self._entries:
            index[normalize_name(entry.name)].append(entry)
        self._name_index = dict(index)

    @classmethod
    def from_files(
        cls,
        weapons_path: str | Path = DEFAULT_WEAPONS_PATH,
        upgrades_path: str | Path = DEFAULT_UPGRADES_PATH,
    ) -> WarframeDatabase:
        return cls(load_json(weapons_path), load_json(upgrades_path))

    @classmethod
    def from_folder(cls, folder: str | Path) -> WarframeDatabase:
        folder = Path(folder)
        return cls.from_files(folder / "weapons.json", folder / "upgrades.json")

    # Preserve the previous private constructor names for existing callers.
    _from_files = from_files
    _from_folder = from_folder

    @overload
    def get(
        self,
        name: str,
        *,
        type: str | None = None,
        attribute: None = None,
    ) -> ArsenalItem | None: ...

    @overload
    def get(
        self,
        name: str,
        *,
        type: str | None = None,
        attribute: str,
    ) -> ArsenalValue | None: ...

    @overload
    def get(
        self,
        name: None = None,
        *,
        type: str | None = None,
        attribute: Literal["name"],
    ) -> list[str]: ...

    @overload
    def get(
        self,
        name: None = None,
        *,
        type: str | None = None,
        attribute: str | None = None,
    ) -> dict[str, ArsenalItem | ArsenalValue | None]: ...

    def get(
        self,
        name: str | None = None,
        *,
        type: str | None = None,
        attribute: str | None = None,
    ) -> ArsenalItem | ArsenalValue | dict[str, ArsenalItem | ArsenalValue | None] | list[str] | None:
        if name is not None:
            matches = [
                entry
                for entry in self._name_index.get(normalize_name(name), ())
                if entry_matches(entry, type)
            ]
            if not matches:
                return None
            if len(matches) > 1:
                categories = ", ".join(sorted(entry.category for entry in matches))
                raise ValueError(
                    f"Ambiguous arsenal item name {name!r}; matching categories: {categories}. "
                    "Pass a more specific type."
                )

            item = self._factory.create(matches[0])
            return self._apply_attribute(item, attribute)

        entries = sorted(
            (entry for entry in self._entries if entry_matches(entry, type)),
            key=lambda entry: normalize_name(entry.name),
        )

        if attribute is not None and normalize_identifier(attribute) == "name":
            return [entry.name for entry in entries]

        result: dict[str, ArsenalItem | ArsenalValue | None] = {}
        for entry in entries:
            item = self._factory.create(entry)
            result[entry.name] = self._apply_attribute(item, attribute)
        return result

    @staticmethod
    def _normalize_sections(
        data: Mapping[str, Any],
        allowed_categories: set[ItemCategory],
    ) -> DatabaseRecords:
        normalized: DatabaseRecords = {}
        for raw_category, entries in data.items():
            category = _SECTION_ALIASES.get(normalize_identifier(raw_category))
            if category not in allowed_categories:
                raise ValueError(f"Unknown database section: {raw_category!r}")
            if not isinstance(entries, dict):
                raise TypeError(f"Database section {raw_category!r} must be a JSON object")
            normalized[category] = entries
        return normalized

    def _iter_database_entries(self) -> Iterable[DatabaseEntry]:
        for category, entries in self.weapons.items():
            for name, data in entries.items():
                yield DatabaseEntry(category=category, name=name, data=data)
        for category, entries in self.upgrades.items():
            for name, data in entries.items():
                yield DatabaseEntry(category=category, name=name, data=data)

    @classmethod
    def _apply_attribute(
        cls,
        item: ArsenalItem,
        attribute: str | None,
    ) -> ArsenalItem | ArsenalValue | None:
        if attribute is None:
            return item
        return cls._extract_attribute(item, attribute)

    @staticmethod
    def _extract_attribute(item: ArsenalItem, attribute: str) -> ArsenalValue | None:
        key = normalize_identifier(attribute)

        if key == "name":
            if isinstance(item, Upgrade):
                return item.name
            return item.stats.base.name

        if isinstance(item, Upgrade):
            key = _ATTRIBUTE_ALIASES.get(key, key)
            if hasattr(item, key):
                return getattr(item, key)
            if key in item.stats:
                return item.stats[key]
            if key in item.conditional_stats:
                return item.conditional_stats[key]
            if key in item.stacking_stats:
                return item.stacking_stats[key]
            return None

        for state_name in ("base", "effective"):
            state = getattr(item.stats, state_name, None)
            if state is not None and hasattr(state, key):
                return getattr(state, key)

        if hasattr(item.stats, key):
            return getattr(item.stats, key)
        if hasattr(item, key):
            return getattr(item, key)
        return None


arsenal = WarframeDatabase.from_files()
