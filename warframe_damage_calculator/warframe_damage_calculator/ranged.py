from __future__ import annotations
from dataclasses import dataclass, field
from .dist import dist
from .weapon import weapon
from .upgrade import upgrade

DOT_MULTIPLIERS = (("slash", 2.1), ("heat", 3.0), ("toxin", 3.0), ("electricity", 3.0), ("gas", 3.0))

@dataclass
class ranged(weapon):
    base_explosion_damage_dist: dist = field(default_factory=dist)
    forced_procs: dist = field(default_factory=dist)
    base_fire_rate: float = 0.0
    base_charge_time: float = 0.0
    base_reload_speed: float = 0.0
    base_magazine_capacity: int = 0
    base_multishot: float = 0.0
    base_weakpoint_damage: float = 3.0
    is_beam: bool = False
    base_explosion_total_damage: float = field(init=False)
    moded_explosion_damage_dist: dist = field(init=False)
    moded_explosion_total_damage: float = field(init=False)
    moded_weakpoint_damage: float = field(init=False)
    moded_multiplicative_fire_rate: float = field(init=False)
    moded_fire_rate: float = field(init=False)
    moded_charge_time: float = field(init=False)
    moded_reload_speed: float = field(init=False)
    moded_magazine_capacity: int = field(init=False)
    moded_multishot: float = field(init=False)
    moded_multiplicative_weakpoint_crit_chance: float = field(init=False)
    moded_weakpoint_crit_chance: float = field(init=False)
    moded_hunter_munitions: float = field(init=False)
    moded_internal_bleeding: float = field(init=False)
    moded_primed_chamber: int = field(init=False)
    moded_vigilante_bonus: float = field(init=False)
    
    def __post_init__(self) -> None:
        self.base_explosion_total_damage = self.base_explosion_damage_dist.total_damage
        super().__post_init__()
    
    def configure(self, *upgrades: upgrade) -> ranged:
        super().configure(*upgrades)
        config = self.config
        self.moded_explosion_damage_dist = self.moded_base_damage * self.base_explosion_damage_dist.apply(config.damage_dist).combine()
        self.moded_explosion_total_damage = self.moded_explosion_damage_dist.total_damage
        self.moded_weakpoint_damage = self.base_weakpoint_damage + config.weakpoint_damage
        self.moded_multiplicative_fire_rate = 1 + config.multiplicative_fire_rate
        self.moded_fire_rate = self.base_fire_rate * (1 + config.fire_rate)
        self.moded_charge_time = self.base_charge_time / (1 + config.fire_rate)
        self.moded_reload_speed = self.base_reload_speed / (1 + config.reload_speed)
        self.moded_magazine_capacity = round(self.base_magazine_capacity * (1 + config.magazine_capacity))
        self.moded_multishot = self.base_multishot * (1 + config.multishot)
        self.moded_multiplicative_weakpoint_crit_chance = 1 + config.multiplicative_weakpoint_crit_chance
        self.moded_weakpoint_crit_chance = self.base_crit_chance * (1 + config.crit_chance + config.weakpoint_crit_chance)
        self.moded_hunter_munitions = config.hunter_munitions
        self.moded_internal_bleeding = config.internal_bleeding * (2 if self.moded_fire_rate * self.moded_multiplicative_fire_rate < 2.5 else 1)
        self.moded_primed_chamber = config.primed_chamber
        self.moded_vigilante_bonus = config.vigilante_bonus
        return self

    def effective_fire_rate(self) -> float:
        if self.moded_magazine_capacity == 1:
            return 1 / self.moded_reload_speed
        return self.moded_magazine_capacity / (self.moded_magazine_capacity * (1 / (self.moded_fire_rate * self.moded_multiplicative_fire_rate) + self.moded_charge_time) + self.moded_reload_speed)

    def effective_crit_chance(self) -> float: # Needs In-Game Testing
        return self.moded_crit_chance * self.moded_multiplicative_crit_chance + self.moded_flat_crit_chance + self.moded_vigilante_bonus
    
    def effective_weakpoint_crit_chance(self) -> float: # Needs In-Game Testing
        return self.moded_weakpoint_crit_chance * (self.moded_multiplicative_crit_chance + self.moded_multiplicative_weakpoint_crit_chance - 1) + self.moded_flat_crit_chance + self.moded_vigilante_bonus

    def effective_status_chance(self) -> float:
        return self.moded_status_chance * self.moded_multishot

    def weakpoint_crit_probability_for_tier(self, tier: int) -> float:
        return max(0, 1 - abs(self.effective_weakpoint_crit_chance() - tier))

    def average_crit_multiplier(self) -> float:
        return 1 + self.effective_crit_chance() * (self.effective_crit_damage() - 1)
    
    def average_weakpoint_crit_multiplier(self) -> float:
        return 1 + self.effective_weakpoint_crit_chance() * (self.effective_crit_damage() - 1)
    
    def average_primed_chamber_multiplier(self) -> float:
        return 1 + self.moded_primed_chamber / self.moded_magazine_capacity
    
    def flat_dph(self) -> float:
        return (self.moded_total_damage * self.moded_multishot + self.moded_explosion_total_damage) * self.moded_faction_damage * self.average_crit_multiplier() * self.average_primed_chamber_multiplier()
    
    def flat_weakpoint_dph(self) -> float:
        return (self.moded_total_damage * self.moded_multishot * self.moded_weakpoint_damage * self.average_weakpoint_crit_multiplier() + self.moded_explosion_total_damage * self.average_crit_multiplier()) * self.moded_faction_damage * self.average_primed_chamber_multiplier()
    
    def flat_dps(self) -> float:
        return self.effective_fire_rate() * self.flat_dph()
    
    def flat_weakpoint_dps(self) -> float:
        return self.effective_fire_rate() * self.flat_weakpoint_dph()
    
    def beam_dot_multiplier(self) -> float:
        return self.moded_multishot if self.is_beam else 1

    def flat_dotph_for(self, damage_dist: dist, crit_chance: float, crit_multiplier: float, include_multishot: bool = True) -> float: # Needs In-Game Testing
        if damage_dist.total_damage <= 0:
            return 0.0
        average_primed_chamber_multiplier = self.average_primed_chamber_multiplier()
        # Hunter munitions
        hunter_munitions_expected_procs = self.moded_hunter_munitions * min(crit_chance, 1)
        hunter_munitions_damage_per_proc = 2.1 * damage_dist.total_damage * max(self.effective_crit_damage(), crit_multiplier) * self.moded_status_damage * self.moded_faction_damage**2 * average_primed_chamber_multiplier
        hunter_munitions_expected_damage = hunter_munitions_expected_procs * hunter_munitions_damage_per_proc
        # Overlap variables
        impact_internal_bleeding = (damage_dist.weight("impact") + self.forced_procs.get("impact")) * self.moded_internal_bleeding
        guaranteed_proc = int(self.moded_status_chance)
        fractional_proc = self.moded_status_chance % 1
        # Internal bleeding
        internal_bleeding_expected_procs = impact_internal_bleeding * self.moded_status_chance
        internal_bleeding_damage_per_proc = 2.1 * damage_dist.total_damage * crit_multiplier * self.moded_status_damage * self.moded_faction_damage**2 * average_primed_chamber_multiplier
        internal_bleeding_expected_damage = internal_bleeding_expected_procs * internal_bleeding_damage_per_proc
        # Hunter munitions & Internal bleeding overlap
        prob_at_least_one_internal_bleeding_proc = 1 - (1 - impact_internal_bleeding) ** guaranteed_proc * ((1 - fractional_proc) + fractional_proc * (1 - impact_internal_bleeding))
        overlap_expected_damage = hunter_munitions_expected_procs * prob_at_least_one_internal_bleeding_proc * min(hunter_munitions_damage_per_proc, internal_bleeding_damage_per_proc)
        # Damage per bullet
        extra_slash_damage_per_bullet = hunter_munitions_expected_damage + internal_bleeding_expected_damage - overlap_expected_damage
        dot_damage_per_bullet = sum(mult * damage_dist.get(dt) * damage_dist.weight(dt) for dt, mult in DOT_MULTIPLIERS) * self.moded_status_chance * crit_multiplier * self.moded_status_damage * self.moded_faction_damage**2 * average_primed_chamber_multiplier
        forced_dot_damage_per_bullet = sum(mult * self.forced_procs.get(dt) * damage_dist.get(dt) for dt, mult in DOT_MULTIPLIERS) * crit_multiplier * self.moded_status_damage * self.moded_faction_damage**2 * average_primed_chamber_multiplier
        # Total dot damage
        return (dot_damage_per_bullet + extra_slash_damage_per_bullet + forced_dot_damage_per_bullet) * (self.moded_multishot * self.beam_dot_multiplier() if include_multishot else 1)

    def flat_dotph(self) -> float:
        direct_damage = self.flat_dotph_for(self.moded_damage_dist, self.effective_crit_chance(), self.average_crit_multiplier())
        explosion_damage = self.flat_dotph_for(self.moded_explosion_damage_dist, self.effective_crit_chance(), self.average_crit_multiplier(), include_multishot=False)
        return direct_damage + explosion_damage

    def flat_weakpoint_dotph(self) -> float:
        direct_damage = self.flat_dotph_for(self.moded_damage_dist, self.effective_weakpoint_crit_chance(), self.average_weakpoint_crit_multiplier())
        explosion_damage = self.flat_dotph_for(self.moded_explosion_damage_dist, self.effective_crit_chance(), self.average_crit_multiplier(), include_multishot=False)
        return direct_damage + explosion_damage

    def flat_dotps(self) -> float:
        return self.effective_fire_rate() * self.flat_dotph()
    
    def flat_weakpoint_dotps(self) -> float:
        return self.effective_fire_rate() * self.flat_weakpoint_dotph()
    
    def total_dph(self) -> float:
        return self.flat_dph() + self.flat_dotph()
    
    def total_weakpoint_dph(self) -> float:
        return self.flat_weakpoint_dph() + self.flat_weakpoint_dotph()
    
    def total_dps(self) -> float:
        return self.flat_dps() + self.flat_dotps()
    
    def total_weakpoint_dps(self) -> float:
        return self.flat_weakpoint_dps() + self.flat_weakpoint_dotps()
    
    def summary(self) -> str:
        return "\n".join([
            f"{'FIRE RATE:':<25} {f'{self.base_fire_rate:.2f}rps':<7} -> {self.moded_fire_rate:.2f}rps",
            f"{'RELOAD SPEED:':<25} {f'{self.base_reload_speed:.2f}s':<7} -> {self.moded_reload_speed:.2f}s",
            f"{'MAGAZINE CAPACITY:':<25} {f'{self.base_magazine_capacity:.0f}r':<7} -> {self.moded_magazine_capacity:.0f}r",
            f"{'MULTISHOT:':<25} {f'{self.base_multishot:.2f}x':<7} -> {self.moded_multishot:.2f}x",
            f"{'CRIT CHANCE | WEAKPOINT:':<25} {f'{self.base_crit_chance:.2%}':<7} -> {self.effective_crit_chance():.2%} | {self.effective_weakpoint_crit_chance():.2%}",
            f"{'CRIT DAMAGE:':<25} {f'{self.base_crit_damage:.2f}x':<7} -> {self.effective_crit_damage():.2f}x",
            f"{'STATUS CHANCE:':<25} {f'{self.base_status_chance:.2%}':<7} -> {self.moded_status_chance:.2%}",
            f"{'STATUS DAMAGE:':<25} {'1.00x':<7} -> {self.moded_status_damage:.2f}x",
            *(f"{f'{dt.upper()}:':<25} {f'{self.base_damage_dist.get(dt):.2f}':<7} -> {self.moded_damage_dist.get(dt):.2f}" for dt, _ in self.moded_damage_dist if self.moded_damage_dist.get(dt) != 0),
            f"{'TOTAL DAMAGE | WEAKPOINT:':<25} {f'{self.base_total_damage * self.base_multishot:.2f}':<7} -> {self.moded_total_damage * self.moded_multishot:.2f} | {self.moded_total_damage * self.moded_multishot * self.moded_weakpoint_damage:.2f}",
            *(f"{f'{dt.upper()}:':<25} {f'{self.base_explosion_damage_dist.get(dt):.2f}':<7} -> {self.moded_explosion_damage_dist.get(dt):.2f}" for dt, _ in self.moded_explosion_damage_dist if self.moded_explosion_damage_dist.get(dt) != 0),
            f"{'TOTAL EXPLOSION DAMAGE:':<25} {f'{self.base_explosion_total_damage:.2f}':<7} -> {self.moded_explosion_total_damage:.2f}",
            "----------------------------------------------------------",
            f"{'EFFECTIVE FIRE RATE:':<25} {self.effective_fire_rate():.2f}rps",
            f"{'EXPECTED PROCS PER SHOT:':<25} {self.effective_status_chance():.2f}",
            f"{'FLAT DPH | WEAKPOINT:':<25} {self.flat_dph():.2f} | {self.flat_weakpoint_dph():.2f}",
            f"{'FLAT DOTPH | WEAKPOINT:':<25} {self.flat_dotph():.2f} | {self.flat_weakpoint_dotph():.2f}",
            f"{'TOTAL DPH | WEAKPOINT:':<25} {self.total_dph():.2f} | {self.total_weakpoint_dph():.2f}",
            f"{'FLAT DPS | WEAKPOINT:':<25} {self.flat_dps():.2f} | {self.flat_weakpoint_dps():.2f}",
            f"{'FLAT DOTPS | WEAKPOINT:':<25} {self.flat_dotps():.2f} | {self.flat_weakpoint_dotps():.2f}",
            f"{'TOTAL DPS | WEAKPOINT:':<25} {self.total_dps():.2f} | {self.total_weakpoint_dps():.2f}",
            "----------------------------------------------------------"
        ])