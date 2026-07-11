from warframe_damage_calculator import arsenal


def test_upgrade_metadata_is_loaded():
    upgrade = arsenal.get("Semi-Pistol Cannonade")

    assert upgrade.name == "Semi-Pistol Cannonade"
    assert upgrade.category == "mod"
    assert upgrade.compatibility == {"pistol"}
    assert upgrade.incompatibility == set()
    assert upgrade.requirements == {"trigger": ["semi"]}
    assert upgrade.max_rank == 5
    assert upgrade.max_stacks is None
    assert upgrade.condition is None
    assert upgrade.is_exilus is False


def test_upgrade_metadata_is_not_scaled_with_rank():
    upgrade = arsenal.get("Amalgam Barrel Diffusion", rank=0)

    assert upgrade.max_rank == 5
    assert upgrade.compatibility == {"pistol"}
    assert upgrade.incompatibility == {"Barrel Diffusion", "Galvanized Diffusion"}
    assert upgrade.multishot == 1.095 / 6


def test_conditional_and_stackable_metadata_is_preserved():
    conditional = arsenal.get("Argon Scope", condition=False)
    stackable = arsenal.get("Berserker Fury", stacks=1)

    assert conditional.condition == "headshot"
    assert conditional.crit_chance == 0.0

    assert stackable.max_stacks == 2
    assert stackable.attack_speed == 0.35


def test_arcane_metadata_defaults_are_loaded():
    upgrade = arsenal.get("Cascadia Accuracy")

    assert upgrade.category == "arcane"
    assert upgrade.compatibility == {"pistol"}
    assert upgrade.incompatibility == set()
    assert upgrade.requirements == {}
    assert upgrade.is_exilus is False
