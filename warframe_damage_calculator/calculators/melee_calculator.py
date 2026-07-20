from ..utils.constants import DOT_MULTIPLIERS
from ..utils.functions import clamp, true_round
from .weapon_calculator import WeaponCalculator


class MeleeCalculator(WeaponCalculator):
    def _compute_modded_stats(self) -> None:
        super()._compute_modded_stats()
        build = self.build.stats.total

        self.modded.attack_speed = max(self.base.attack_speed * (1 + build.attack_speed), 0)
        self.modded.melee_duplicate = clamp(build.melee_duplicate, 0, 1)
        self.modded.melee_doughty = clamp(build.melee_doughty, 0, 1)

    def _compute_effective_stats(self) -> None:
        super()._compute_effective_stats()
        self.effective.attack_speed = self.modded.attack_speed
        self.effective.melee_duplicate = self.modded.melee_duplicate
        self.effective.melee_doughty = self.modded.melee_doughty

    def _compute_average_stats(self) -> None:
        super()._compute_average_stats()
        damage = self.effective.damage

        self.average.melee_doughty_bonus = true_round(10 * self.effective.damage.weight("puncture") * self.effective.status_chance * self.effective.melee_doughty, 1)
        self.average.melee_duplicate_multiplier = 1 + self.effective.melee_duplicate * max(0, 1 - abs(self.effective.crit_chance - 1))
        self.average.flat_dph = self.effective.damage.total_damage() * self.effective.faction_damage * self.average.crit_multiplier * self.average.melee_duplicate_multiplier
        self.average.flat_dps = self.effective.attack_speed * self.average.flat_dph
        self.average.flat_dotph = sum(multiplier * damage.get(damage_type) * damage.weight(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * self.effective.status_chance * self.effective.status_damage * self.effective.faction_damage ** 2 * self.average.crit_multiplier * self.average.melee_duplicate_multiplier
        self.average.flat_dotps = self.effective.attack_speed * self.average.flat_dotph
        self.average.total_dph = self.average.flat_dph + self.average.flat_dotph
        self.average.total_dps = self.average.flat_dps + self.average.flat_dotps
