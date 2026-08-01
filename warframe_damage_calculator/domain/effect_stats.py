from .status import STATUS_TYPES


STATUS_PROC_STATS = frozenset(f"{kind}_proc" for kind in STATUS_TYPES)
MULTIPLICATIVE_EFFECT_STATS = frozenset({"range", "explosion_radius", "slam_radius"})
HANDLED_EFFECT_STATS = frozenset({
    "accuracy", "afflictions_proc_multiplier", "ammo_efficiency", "ammo_maximum", "area_of_effect", "armor_reduction", "attack_speed", "bleed_on_impact",
    "cascadia_empowered_proc", "cold", "condition_overload", "corpus_damage", "corrosive", "crit_chance", "crit_damage", "crit_from_status",
    "crit_reset_charges", "crit_tier", "damage", "damage_bonus", "debilitate_proc_chance", "duplicated_hit", "electricity", "explosion_radius",
    "fire_rate", "fire_rate_lock", "gas", "grineer_damage", "heat", "heavy_attack_efficiency", "heavy_attack_speed", "impact",
    "impact_to_puncture_conversion", "infested_damage", "initial_combo", "magazine_capacity", "magnetic", "multishot", "multishot_lock",
    "murmur_damage", "noise_level", "orokin_damage", "overguard_damage_multiplier", "projectile_speed", "puncture", "puncture_proc",
    "punch_through", "radiation", "random_proc", "range", "recoil", "reload_speed", "sentient_damage", "sharpshot_bonus", "slam_damage",
    "slam_radius", "slash", "slash_proc", "status_chance", "status_damage", "status_duration", "status_from_crit", "status_vulnerability",
    "toxin", "unique_enemy_vulnerability_multiplier", "viral", "weakpoint_crit_chance", "weakpoint_damage", "zoom",
})
NON_CALCULATION_EFFECT_STATS = frozenset({
    "aerial_melee_attack_range", "ammo_efficiency_chance", "ammo_replenish_chance", "ammo_restore", "body_shot_crit_chance_multiplier",
    "bullet_jump", "combo_count", "combo_duration", "combo_gain_chance", "combo_on_ammo_pickup", "combo_on_finisher", "combo_timer_pause",
    "damage_field_duration", "double_jump_strength", "extra_jump", "finisher_damage", "follow_through", "health_regen", "holstered_reload",
    "incarnon_charge_rate", "instant_reload_chance", "magazine_restore_chance", "movement_speed", "movement_speed_while_aiming", "overshield",
    "parkour_velocity", "parry_angle", "slide", "slide_attack_range", "sprint_speed", "stun_on_finisher",
})


def unclassified_effect_stats(stats: set[str]) -> set[str]:
    return stats - HANDLED_EFFECT_STATS - NON_CALCULATION_EFFECT_STATS
