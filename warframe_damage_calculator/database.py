from __future__ import annotations

import difflib
import json
from pathlib import Path
from warnings import warn
import sys

from .constants import UPGRADE_TABLES, WEAPON_TABLES
from .states import MeleeState, PrimaryState, SecondaryState
from .dist import Dist
from .upgrade import Upgrade
from .melee import Melee
from .primary import Primary
from .secondary import Secondary

class Database:
    def __init__(self, root: Path | None = None) -> None:
        base_root = root or Path(__file__).resolve().parents[1] / "database"
        filenames = {"primary": "primaries.json", "secondary": "secondaries.json", "melee": "melees.json", "mod": "mods.json", "arcane": "arcanes.json"}
        self.tables = {table: json.loads((base_root / filename).read_text(encoding="utf-8")) for table, filename in filenames.items()}

    @staticmethod
    def add(mapping: dict[str, float], key: str, value: float) -> None:
        mapping[key] = mapping.get(key, 0.0) + value

    def suggest(self, tables: tuple[str, ...], name: str, cutoff: float = 0.6) -> str | None:
        choices = [candidate for table in tables for candidate in self.tables[table]]
        lower_to_choice = {choice.lower(): choice for choice in choices}
        matches = difflib.get_close_matches(name.lower(), list(lower_to_choice), n=1, cutoff=cutoff)
        if not matches:
            return None
        return lower_to_choice[matches[0]]

    def find(self, tables: tuple[str, ...], name: str) -> tuple[str, dict]:
        for table in tables:
            if (record := self.tables[table].get(name)) is not None:
                return table, record
        suggestion = self.suggest(tables, name)
        if suggestion is None:
            sys.exit(f"ERROR: '{name}' not found")
        sys.exit(f"ERROR: '{name}' not found, did you mean '{suggestion}'?")

    def weapon(self, name: str) -> Melee | Primary | Secondary:
        table, record = self.find(WEAPON_TABLES, name)
        weapon_common = dict(damage_dist=Dist(**record.get("damage_dist", {})), forced_procs=Dist(**record.get("forced_procs", {})), crit_chance=record.get("crit_chance", 0.0), crit_damage=record.get("crit_damage", 0.0), status_chance=record.get("status_chance", 0.0))
        if table == "melee":
            return Melee(base=MeleeState(**weapon_common, attack_speed=record.get("attack_speed", 0.0)))
        ranged_common = dict(weapon_common, explosion_damage_dist=Dist(**record.get("explosion_damage_dist", {})), explosion_forced_procs=Dist(**record.get("explosion_forced_procs", {})), fire_rate=record.get("fire_rate", 0.0), charge_time=record.get("charge_time", 0.0), reload_speed=record.get("reload_speed", 0.0), magazine_capacity=record.get("magazine_capacity", 0), multishot=record.get("multishot", 1.0), weakpoint_damage=record.get("weakpoint_damage", 3.0), is_beam=record.get("is_beam", False))
        if table == "primary":
            return Primary(base=PrimaryState(**ranged_common))
        if table == "secondary":
            return Secondary(base=SecondaryState(**ranged_common))
        raise RuntimeError(f"Unknown weapon table {table}")

    def upgrade(self, name: str, rank: int | None = None, stacks: int | None = None, conditional: bool | None = None) -> Upgrade:
        _, record = self.find(UPGRADE_TABLES, name)
        max_rank = record.get("max_rank", None)
        max_stacks = record.get("max_stacks", None)
        
        if rank == None: rank = max_rank
        elif rank < 0: raise ValueError(f"Rank should be greater than 0, got {rank}")
        elif rank > max_rank: print(f"WARNING: Max rank exceded on {name}: Max rank is {max_rank}, got {rank}")

        if stacks == None: stacks = max_stacks
        elif stacks < 0: raise ValueError(f"Stacks should be greater than 0, got {stacks}")
        elif stacks > max_stacks: print(f"WARNING: Max stacks exceded on {name}: Max stacks is {max_stacks}, got {stacks}")

        if conditional == None: conditional = 1
        elif isinstance(conditional, bool): conditional = int(conditional)

        damage_dist: dict[str, float] = {}
        stats: dict[str, float] = {}

        for key, value in record.items():
            if key == "max_rank": continue
            if key == "max_stacks": continue
            if key == "compatible_weapons": continue
            multiplier = 1
            if key.startswith("stacking_"):
                multiplier = stacks
                key = key.removeprefix("stacking_")
            elif key.startswith("conditional_"):
                multiplier = conditional
                key = key.removeprefix("conditional_")
            if key == "damage_dist":
                for damage_type, series in value.items():
                    rank_series = float(series[max(0, min(rank, len(series) - 1))])
                    self.add(damage_dist, damage_type, multiplier * rank_series)
            elif isinstance(value, list):
                rank_value = float(value[max(0, min(rank, len(value) - 1))])
                self.add(stats, key, multiplier * rank_value)
            elif isinstance(value, bool):
                stats[key] = bool(value)
            else:
                self.add(stats, key, multiplier * float(value))

        return Upgrade(damage_dist=Dist(**damage_dist), **stats)

default_database = Database()

def load_weapon(name: str) -> Melee | Primary | Secondary:
    return default_database.weapon(name)

def load_upgrade(name: str, rank: int | None = None, stacks: int | None = None, conditional: bool | None = None) -> Upgrade:
    return default_database.upgrade(name, rank, stacks, conditional)