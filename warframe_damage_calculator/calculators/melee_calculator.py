from __future__ import annotations

from functools import cached_property

from ..utils import DOT_MULTIPLIERS, true_round, clamp
from ..states import MeleeState
from .weapon_calculator import WeaponCalculator


class MeleeCalculator(WeaponCalculator[MeleeState]):
    def __init__(self, base: MeleeState) -> None:
        super().__init__(base)

    def _compute_moded_stats(self) -> None:
        super()._compute_moded_stats()
        self.moded.attack_speed = max(self.base.attack_speed * (1 + self.build.attack_speed), 0)
        self.moded.melee_duplicate = clamp(self.build.melee_duplicate, 0, 1)
        self.moded.melee_doughty = clamp(self.build.melee_doughty, 0, 1)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.attack_speed = self.moded.attack_speed
        self.effective.melee_duplicate = self.moded.melee_duplicate
        self.effective.melee_doughty = self.moded.melee_doughty

    @cached_property
    def melee_doughty_bonus(self) -> float:
        return true_round(10 * self.effective.damage_dist.weight("puncture") * self.effective.status_chance * self.effective.melee_doughty, 1)

    @cached_property
    def average_melee_duplicate_multiplier(self) -> float:
        return 1 + self.effective.melee_duplicate * max(0, 1 - abs(self.effective.crit_chance - 1))

    @cached_property
    def flat_dph(self) -> float:
        return self.effective.total_damage * self.effective.faction_damage * self.average_crit_multiplier * self.average_melee_duplicate_multiplier

    @cached_property
    def flat_dps(self) -> float:
        return self.effective.attack_speed * self.flat_dph

    @cached_property
    def flat_dotph(self) -> float:
        return sum(mult * self.effective.damage_dist.get(dt) * self.effective.damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.effective.status_chance * self.effective.status_damage * self.effective.faction_damage ** 2 * self.average_crit_multiplier * self.average_melee_duplicate_multiplier

    @cached_property
    def flat_dotps(self) -> float:
        return self.effective.attack_speed * self.flat_dotph
