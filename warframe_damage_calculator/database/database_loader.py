from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Literal

from ..models import Melee, Primary, Secondary, Upgrade, dist


UpgradeKind = Literal["mod", "arcane"]
WeaponKind = Literal["primary", "secondary", "melee"]

RANGED_FIELDS = {
    "damage_dist",
    "forced_procs",
    "crit_chance",
    "crit_damage",
    "status_chance",
    "is_beam",
    "is_battery",
    "explosion_damage_dist",
    "explosion_forced_procs",
    "multishot",
    "fire_rate",
    "burst_count",
    "burst_delay",
    "charge_time",
    "reload_speed",
    "recharge_rate",
    "magazine_capacity",
    "weakpoint_damage",
}

MELEE_FIELDS = {
    "damage_dist",
    "forced_procs",
    "crit_chance",
    "crit_damage",
    "status_chance",
    "attack_speed",
}


def normalized_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _database_dir() -> Path:
    package_dir = Path(__file__).resolve().parent
    candidates = (
        package_dir / "database" / "generated",
        package_dir.parent / "database" / "generated",
        Path.cwd() / "database" / "generated",
    )

    filenames = ("mods.json", "arcanes.json", "primaries.json", "secondaries.json", "melees.json")

    for candidate in candidates:
        if all((candidate / filename).exists() for filename in filenames):
            return candidate

    raise FileNotFoundError("Could not find generated database files.")


@cache
def _load_database_file(filename: str) -> dict[str, dict]:
    with open(_database_dir() / filename, encoding="utf8") as file:
        return json.load(file)


def _load_mod_record(name: str, kind: UpgradeKind) -> dict:
    key = normalized_key(name)
    sources = []

    if kind == "mod":
        sources.append(_load_database_file("mods.json"))

    elif kind == "arcane":
        sources.append(_load_database_file("arcanes.json"))

    for source in sources:
        record = source.get(key)

        if record is not None:
            return record

    raise KeyError(f"Unknown {kind}: {name}")


def _load_weapon_record(name: str, kind: WeaponKind):
    key = normalized_key(name)
    sources = []

    if kind == "primary":
        sources.append((_load_database_file("primaries.json"), Primary, RANGED_FIELDS))

    elif kind == "secondary":
        sources.append((_load_database_file("secondaries.json"), Secondary, RANGED_FIELDS))

    elif kind == "melee":
        sources.append((_load_database_file("melees.json"), Melee, MELEE_FIELDS))

    for source, weapon_class, fields in sources:
        record = source.get(key)

        if record is not None:
            return record, weapon_class, fields

    raise KeyError(f"Unknown {kind}: {name}")


def _rank_multiplier(rank: int, max_rank: int) -> float:
    if not isinstance(rank, int):
        raise TypeError("rank must be an integer")

    if rank < 0 or rank > max_rank:
        raise ValueError(f"rank must be between 0 and {max_rank}")

    return (rank + 1) / (max_rank + 1) if max_rank > 0 else 1.0


def _stack_count(stacks: int, max_stacks: int | None) -> int:
    if not isinstance(stacks, int):
        raise TypeError("stacks must be an integer")

    if stacks < 0:
        raise ValueError("stacks cannot be negative")

    if max_stacks is not None and stacks > max_stacks:
        raise ValueError(f"stacks must be between 0 and {max_stacks}")

    return stacks


def _add_upgrade_stat(stats: dict, name: str, value) -> None:
    if isinstance(value, dict):
        current = stats.setdefault(name, {})

        for damage_type, amount in value.items():
            current[damage_type] = current.get(damage_type, 0.0) + amount

        return

    if isinstance(value, bool):
        stats[name] = stats.get(name, False) or value
        return

    stats[name] = stats.get(name, 0.0) + value


def _scale_value(value, multiplier: float):
    if isinstance(value, dict):
        return {damage_type: amount * multiplier for damage_type, amount in value.items()}

    if isinstance(value, bool):
        return value

    return value * multiplier


def _to_upgrade_kwargs(record: dict, rank: int, stacks: int) -> dict:
    max_rank = int(record.get("max_rank", 0))
    max_stacks = record.get("max_stacks")
    rank_multiplier = _rank_multiplier(rank, max_rank)
    stack_count = _stack_count(stacks, max_stacks)
    stats = {}

    for stat_name, value in record.get("stats", {}).items():
        multiplier = rank_multiplier
        output_name = stat_name

        if stat_name.startswith("stackable_"):
            output_name = stat_name.removeprefix("stackable_")
            multiplier *= stack_count

        elif stat_name.startswith("conditional_"):
            output_name = stat_name.removeprefix("conditional_")

            if record.get("condition") == "max rank" and rank != max_rank:
                continue

        _add_upgrade_stat(stats, output_name, _scale_value(value, multiplier))

    damage_dist = stats.pop("damage_dist", None)

    if damage_dist is not None:
        stats["damage_dist"] = dist(**damage_dist)

    return stats


def _to_weapon_kwargs(record: dict, fields: set[str]) -> dict:
    kwargs = {field: record[field] for field in fields if field in record}

    for field in ("damage_dist", "forced_procs", "explosion_damage_dist", "explosion_forced_procs"):
        if field in kwargs:
            kwargs[field] = dist(**kwargs[field])

    return kwargs


def load_mod(name: str, rank: int | None = None, stacks: int = 0) -> Upgrade:
    record = _load_mod_record(name, "mod")
    max_rank = int(record.get("max_rank", 0))
    resolved_rank = max_rank if rank is None else rank
    return Upgrade(name=str(name), **_to_upgrade_kwargs(record, resolved_rank, stacks))


def load_arcane(name: str, rank: int | None = None, stacks: int = 0) -> Upgrade:
    record = _load_mod_record(name, "arcane")
    max_rank = int(record.get("max_rank", 0))
    resolved_rank = max_rank if rank is None else rank
    return Upgrade(name=str(name), **_to_upgrade_kwargs(record, resolved_rank, stacks))


def load_primary(name: str) -> Primary:
    record, weapon_class, fields = _load_weapon_record(name, "primary")
    return weapon_class(**_to_weapon_kwargs(record, fields))


def load_secondary(name: str) -> Secondary:
    record, weapon_class, fields = _load_weapon_record(name, "secondary")
    return weapon_class(**_to_weapon_kwargs(record, fields))


def load_melee(name: str) -> Melee:
    record, weapon_class, fields = _load_weapon_record(name, "melee")
    return weapon_class(**_to_weapon_kwargs(record, fields))


__all__ = [
    "load_mod",
    "load_arcane",
    "load_primary",
    "load_secondary",
    "load_melee",
]