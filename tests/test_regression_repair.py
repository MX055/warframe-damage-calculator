from warframe_damage_calculator import Build, arsenal
from warframe_damage_calculator.engine import formulas


def selected(weapon):
    return weapon.results.main


def test_missing_upgrade_metadata_restored():
    assert arsenal.get('Ammo Drum').data.stats.ammo_maximum == [{'value': 0.9}]
    assert arsenal.get('Eagle Eye').data.stats.zoom == [{'value': 0.4}]
    assert arsenal.get('Spectral Serration').data.stats.damage_bonus == [{'value': 3.3, 'when': 'invisible'}]


def test_weapon_metadata_and_evolution_behaviors_restored():
    assert selected(arsenal.get('Dread')).effective.noise_level == 'silent'
    braton = arsenal.get('Braton').set({'evolutions': {2: 2}})
    assert formulas.multishot_consumes_ammo_enabled(selected(braton).evolutions)
    laetum = arsenal.get('Laetum').set({'evolutions': {5: 1}})
    result = selected(laetum)
    assert result.evolutions.proportional.non_crit_bonus_chance == 0.5
    assert result.evolutions.multiplicative_families['non_crit'].damage_bonus == 20


def test_new_behavior_features_remain_canonical():
    frostbite = arsenal.upgrades['Primary Frostbite']['stats']['crit_damage'][0]
    assert frostbite['behavior'] == 'STATUS_EFFECT_STACKS'
    acuity = Build(arsenal.get('Primary Acuity'))
    assert acuity.results.total.multiplicative_families['bonus'].weakpoint_crit_chance == 3.5
