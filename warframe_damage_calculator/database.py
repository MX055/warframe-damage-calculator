from __future__ import annotations

import json
from pathlib import Path

from .constants import UPGRADE_TABLES, WEAPON_TABLES
from .dist import Dist
from .melee import Melee
from .primary import Primary
from .secondary import Secondary
from .upgrade import Upgrade

class Database:
    def __init__(self, root: Path | None = None) -> None:
        base_root = root or Path(__file__).resolve().parents[1] / "database"
        filenames = {"primary": "primaries.json", "secondary": "secondaries.json", "melee": "melees.json", "mod": "mods.json", "arcane": "arcanes.json"}
        self.tables = {table: json.loads((base_root / filename).read_text(encoding="utf-8")) for table, filename in filenames.items()}

    @staticmethod
    def rank_value(value: object, rank: int | None) -> float:
        if not value: return 0.0
        if not isinstance(value, list): return float(value)
        if rank is None: rank = len(value) - 1
        return float(value[max(0, min(rank, len(value) - 1))])

    @staticmethod
    def add(mapping: dict[str, float], key: str, value: float) -> None:
        mapping[key] = mapping.get(key, 0.0) + value

    def find(self, tables: tuple[str], name: str) -> tuple[str, dict]:
        for table in tables:
            if (record := self.tables[table].get(name)) is not None:
                return table, record
        raise KeyError(f"Unknown object: {name}")

    def weapon(self, name: str) -> Melee | Primary | Secondary:
        table, record = self.find(WEAPON_TABLES, name)
        weapon_common = dict(base_damage_dist=Dist(**record.get("damage_dist", {})), forced_procs=Dist(**record.get("forced_procs", {})), base_crit_chance=record.get("crit_chance", 0.0), base_crit_damage=record.get("crit_damage", 0.0), base_status_chance=record.get("status_chance", 0.0))
        if table == "melee":
            return Melee(**weapon_common, base_attack_speed=record.get("attack_speed", 0.0))
        ranged_common = dict(weapon_common, base_explosion_damage_dist=Dist(**record.get("explosion_damage_dist", {})), explosion_forced_procs=Dist(**record.get("explosion_forced_procs", {})), base_fire_rate=record.get("fire_rate", 0.0), base_charge_time=record.get("charge_time", 0.0), base_reload_speed=record.get("reload_speed", 0.0), base_magazine_capacity=record.get("magazine_capacity", 0), base_multishot=record.get("multishot", 1.0), is_beam=record.get("is_beam", False))
        if table == "primary":
            return Primary(**ranged_common)
        if table == "secondary":
            return Secondary(**ranged_common)
        raise RuntimeError(f"Unknown weapon table {table}")

    def upgrade(self, name: str, rank: int | None = None, stacks: int | None = None, conditional: bool | None = None) -> Upgrade:
        _, record = self.find(UPGRADE_TABLES, name)
        max_stacks = record.get("max_stacks", 1)
        stack_count = max(0, min(max_stacks if stacks is None else stacks, max_stacks))
        damage_dist: dict[str, float] = {}
        stats: dict[str, float] = {}

        for key, value in record.items():
            if key == "max_stacks": continue
            multiplier = 1
            if key.startswith("stack_"):
                multiplier = stack_count
                key = key.removeprefix("stack_")
            elif key.startswith("conditional_"):
                if conditional is False: continue
                key = key.removeprefix("conditional_")
            if key == "damage_dist":
                for damage_type, series in value.items():
                    self.add(damage_dist, damage_type, multiplier * self.rank_value(series, rank))
            else: self.add(stats, key, multiplier * self.rank_value(value, rank))

        return Upgrade(damage_dist=Dist(**damage_dist), **stats)

default_database = Database()

def load_weapon(name: str) -> Melee | Primary | Secondary:
    return default_database.weapon(name)

def load_upgrade(name: str, rank: int | None = None, stacks: int | None = None, conditional: bool | None = None) -> Upgrade:
    return default_database.upgrade(name, rank, stacks, conditional)