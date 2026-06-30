from __future__ import annotations

import json
import tempfile
from pathlib import Path

from warframe_damage_calculator import Dist, Secondary
from warframe_damage_calculator.database import Database
from warframe_damage_calculator.ranged import Ranged


class TestRanged(Ranged):
    def flat_dotph_for(self, damage_dist: Dist, forced_procs: Dist, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float:
        return Secondary.flat_dotph_for(self, damage_dist, forced_procs, crit_chance, crit_multiplier, include_multishot)


def make_database_fixture() -> tuple[Database, tempfile.TemporaryDirectory[str]]:
    tempdir = tempfile.TemporaryDirectory()
    root = Path(tempdir.name)

    tables = {
        "primaries.json": {
            "Test Primary": {
                "damage_dist": {"impact": 10, "slash": 5},
                "forced_procs": {"impact": 1},
                "crit_chance": 0.5,
                "crit_damage": 2.0,
                "status_chance": 0.25,
                "explosion_damage_dist": {"heat": 4},
                "explosion_forced_procs": {"cold": 1},
                "weakpoint_damage": 3.0,
                "fire_rate": 2.0,
                "reload_speed": 4.0,
                "magazine_capacity": 5,
                "multishot": 2.0,
                "is_beam": True,
            }
        },
        "secondaries.json": {
            "Test Secondary": {
                "damage_dist": {"impact": 10, "slash": 5},
                "forced_procs": {"impact": 1},
                "crit_chance": 0.5,
                "crit_damage": 2.0,
                "status_chance": 0.25,
                "explosion_damage_dist": {"heat": 4},
                "explosion_forced_procs": {"cold": 1},
                "weakpoint_damage": 3.0,
                "fire_rate": 2.0,
                "reload_speed": 4.0,
                "magazine_capacity": 5,
                "multishot": 2.0,
                "is_beam": False,
            }
        },
        "melees.json": {
            "Test Melee": {
                "damage_dist": {"impact": 10, "slash": 5},
                "forced_procs": {},
                "crit_chance": 0.5,
                "crit_damage": 2.0,
                "status_chance": 0.25,
                "attack_speed": 2.0,
            }
        },
        "mods.json": {
            "Test Mod": {
                "max_rank": 2,
                "max_stacks": 3,
                "damage_dist": {"impact": [0, 1, 2]},
                "base_damage": [0, 0.5, 1.0],
                "stacking_status_chance": [0.0, 0.1, 0.2, 0.3],
                "conditional_crit_chance": [0.0, 0.25, 0.5],
                "fire_rate_lock": True,
                "multishot": 0.2,
            }
        },
        "arcanes.json": {
            "Test Arcane": {
                "max_rank": 3,
                "base_damage": [0.0, 0.1, 0.2, 0.3],
                "reload_speed": 0.25,
            }
        },
    }

    for filename, data in tables.items():
        (root / filename).write_text(json.dumps(data), encoding="utf-8")

    return Database(root), tempdir