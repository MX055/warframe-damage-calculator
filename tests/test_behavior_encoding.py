from warframe_damage_calculator import Upgrade, arsenal


def test_bundled_special_effects_use_behavior_schema():
    expected = {
        "Hunter Munitions": ("slash_proc", "ON_CRIT"),
        "Internal Bleeding": ("slash_proc", "ON_IMPACT_DOUBLE_BELOW_2_5_FR"),
        "Primed Chamber": ("damage_bonus", "FIRST_SHOT"),
        "Secondary Encumber": ("random_proc", "ON_ANY_PROC"),
        "Secondary Enervate": ("crit_reset_charges", "STACK_RESET_CRIT_2_PLUS"),
        "Melee Duplicate": ("duplicated_hit", "NEAR_YELLOW"),
        "Melee Doughty": ("crit_damage", "FROM_PUNCTURE_X_STATUS"),
        "Vigilante Supplies": ("crit_chance", "ON_HIT"),
    }
    for name, (stat, behavior) in expected.items():
        effects = arsenal.get(name).data.stats[stat]
        assert effects[0]["behavior"] == behavior


def test_legacy_pseudo_stats_are_migrated_at_runtime():
    upgrade = Upgrade({
        "name": "Legacy Hunter Munitions",
        "type": "mod",
        "max_rank": 0,
        "stats": {"hunter_munitions": [{"value": 0.3}]},
        "runtime": {"rank": 0},
    })
    entries = upgrade.results.total.application_chance
    assert entries[0]["stat"] == "slash_proc"
    assert entries[0]["behavior"] == "ON_CRIT"
    assert entries[0]["chance"] == 0.3
