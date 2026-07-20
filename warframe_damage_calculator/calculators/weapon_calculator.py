from typing import Any

from ..models.build import Build
from ..models.dist import Dist
from ..models.fields import AverageStats, CalculatedStats
from ..models.upgrade import Upgrade


class WeaponCalculator:
    def __init__(self, weapon: Any) -> None:
        self.weapon = weapon
        self.resolved_build = Build()
        self.base = CalculatedStats()
        self.modded = CalculatedStats()
        self.effective = CalculatedStats()
        self.average = AverageStats()
        self.recompute()

    @staticmethod
    def _condition_overload_bonus(build: Any, damage: Dist, forced_procs: Dist, co_factor: float) -> float:
        condition_overload = build.condition_overload
        statuses = set(damage.data) | {status for status, count in forced_procs if count > 0}
        stacks = len(statuses) if condition_overload.max_stacks == "inf" else min(len(statuses), int(condition_overload.max_stacks))
        return float(condition_overload.value) * stacks * co_factor

    def _compute_modded_stats(self) -> None:
        build = self.resolved_build.stats.total
        damage = self.base.damage.apply(build.damage).combine().sorted()
        co_bonus = self._condition_overload_bonus(build, damage, self.base.forced_procs, self.weapon.mode.stats.co_factor)
        self.modded.multiplicative_base_damage = max(1 + build.multiplicative_base_damage + (co_bonus if self.weapon.mode.stats.co_effect == "multiplies" else 0), 1)
        self.modded.base_damage = max(1 + build.base_damage + (co_bonus if self.weapon.mode.stats.co_effect != "multiplies" else 0), 0)
        self.modded.damage = self.modded.base_damage * damage
        faction_damage = max(build.corpus_damage, build.grineer_damage, build.infested_damage, build.orokin_damage, build.murmur_damage, build.sentient_damage)
        self.modded.faction_damage = max(1 + faction_damage, 1)
        self.modded.flat_crit_chance = max(build.flat_crit_chance, 0)
        self.modded.multiplicative_crit_chance = max(1 + build.multiplicative_crit_chance, 1)
        self.modded.crit_chance = max(self.base.crit_chance * (1 + build.crit_chance), 0)
        self.modded.flat_crit_damage = max(build.flat_crit_damage, 0)
        self.modded.crit_damage = max(self.base.crit_damage * (1 + build.crit_damage), 1)
        self.modded.status_chance = max(self.base.status_chance * (1 + build.status_chance), 0)
        self.modded.status_damage = max(1 + build.status_damage, 1)

    def _compute_effective_stats(self) -> None:
        self.effective.base_damage = self.modded.base_damage * self.modded.multiplicative_base_damage
        self.effective.damage = self.modded.multiplicative_base_damage * self.modded.damage
        self.effective.faction_damage = self.modded.faction_damage
        self.effective.crit_chance = self.modded.crit_chance * self.modded.multiplicative_crit_chance + self.modded.flat_crit_chance
        self.effective.crit_damage = self.modded.crit_damage + self.modded.flat_crit_damage
        self.effective.status_chance = self.modded.status_chance
        self.effective.status_damage = self.modded.status_damage

    def _compute_average_stats(self) -> None:
        self.average.crit_chance = self.effective.crit_chance
        self.average.crit_multiplier = 1 + self.average.crit_chance * (self.effective.crit_damage - 1)

    def recompute(self) -> None:
        stats = dict(self.weapon.mode.stats)
        ammo = self.weapon.data.entry.ammo
        stats.update({"magazine_capacity": ammo.get("magazine_size", 1), "reload_speed": ammo.get("reload_time", 0), "recharge_rate": ammo.get("recharge_rate", 0)})
        if self.weapon.data.entry.type == "melee":
            stats["attack_speed"] = self.weapon.mode.stats.fire_rate
        self.base = CalculatedStats(self.weapon.mode_stats_type(stats).with_defaults())
        evolutions = (
            Upgrade(
                {f"{evolution} perk {perk}": {
                    "type": "evolution",
                    "max_rank": 0,
                    "compatibility": {"types": []},
                    "stats": self.weapon.data.entry.evolutions[evolution.removeprefix("evolution_")][str(perk)].get("stats", {}),
                }},
            )
            for evolution, perk in self.weapon.evolutions.items()
        )
        self.resolved_build = Build(*self.weapon.build, *evolutions)
        entry = self.weapon.data.entry
        context = {
            "name": self.weapon.data.name,
            "type": entry.type,
            "subtype": entry.subtype,
            "trigger": self.weapon.mode.get("trigger"),
            "projectile": self.weapon.mode.get("delivery"),
            "aoe": self.weapon.mode.get("aoe", False),
        }
        self.resolved_build.stats.resolve({"context": context})
        self._compute_modded_stats()
        self._compute_effective_stats()
        self._compute_average_stats()

    def contribution(self, upgrade: Upgrade) -> float:
        full = self.weapon.build
        if all(equipped.data != upgrade.data for equipped in full):
            return 0.0
        reduced = full - upgrade
        full_dps = self.average.total_dps
        try:
            self.weapon.configure(reduced)
            return full_dps - self.average.total_dps
        finally:
            self.weapon.configure(full)

    def contribution_values(self) -> dict[str, float]:
        return {str(upgrade.data.name): self.contribution(upgrade) for upgrade in self.weapon.build}

    def contribution_proportions(self) -> dict[str, float]:
        contributions = self.contribution_values()
        total = sum(contributions.values()) or 1
        return {name: contribution / total for name, contribution in contributions.items()}
