from typing import get_args

import pytest

from warframe_damage_calculator import Build, Data, Primary, Upgrade, arsenal
from warframe_damage_calculator.models.dist import Dist
from warframe_damage_calculator.models.weapon import Weapon
from warframe_damage_calculator.utils.types import DamageType


def test_loader_context_and_attributes():
    upgrade = arsenal.get("Serration", context={"rank": 2})
    assert upgrade.data.context.rank == 2
    assert arsenal.get("Serration", attribute="name") == "Serration"
    assert arsenal.get("Serration", attribute="base_damage") is not None


def test_data_copy_is_independent():
    original = Data({"nested": {"items": [{"value": 1}]}, "damage": {"impact": 2}})
    copied = original.copy()
    copied.nested["items"][0].value = 3
    copied.damage.impact = 4
    assert original.nested["items"][0].value == 1
    assert original.damage.impact == 2


def test_calculator_normalizes_damage_distributions():
    stats = {field: {"impact": 1} for field in ("damage", "forced_procs", "explosion_damage", "explosion_forced_procs")}
    data = Data({"stats": stats, "context": {}})
    calculator = Weapon(data).stats
    assert all(isinstance(calculator.base[field], Dist) for field in ("damage", "forced_procs"))
    assert all(isinstance(data.stats[field], Data) for field in stats)
    ranged = Primary(data)
    assert all(isinstance(ranged.stats.base[field], Dist) for field in stats)
    assert isinstance(Upgrade({"stats": {"heat": 1}}).stats.total.damage, Dist)


def test_dist_filters_accept_generators():
    damage = Dist({"impact": 1, "puncture": 2, "slash": 3})
    assert dict(damage) == {"impact": 1, "puncture": 2, "slash": 3}
    assert damage.include(item for item in ("impact", "slash")) == Dist({"impact": 1, "slash": 3})
    assert damage.exclude(item for item in ("impact", "slash")) == Dist({"puncture": 2})


def test_build_aggregation():
    build = Build(
        Upgrade({"stats": {"base_damage": 0.5, "enabled": False}}),
        Upgrade({"stats": {"base_damage": 0.25, "enabled": True}}),
    )
    assert build.stats.total == {"base_damage": 0.75, "enabled": True}


def test_native_multishot_status_chance_is_per_projectile():
    weapon = arsenal.get("Corinth Prime")

    assert weapon.stats.base.status_chance == pytest.approx(0.09)
    assert weapon.stats.base.multishot == 6
    assert weapon.stats.average.procs_per_shot == pytest.approx(0.54)


def test_negative_physical_damage_modifier_is_applied_before_filtering():
    weapon = Primary({"stats": {"damage": {"impact": 100}}})

    weapon.configure(Upgrade({"stats": {"impact": -0.5}}))

    assert weapon.stats.effective.damage == Dist({"impact": 50})


def test_explosion_summary_iterates_damage_type_keys():
    weapon = Primary({"stats": {"damage": {"impact": 1}, "explosion_damage": {"heat": 10}}})

    summary = weapon.format.summary()

    assert "HEAT:" in summary
    assert "10.00" in summary


def test_multi_element_damage_order_is_deterministic_across_resolvers():
    combined = Upgrade({"stats": {
        "damage": [{"cold": 1}, {"toxin": 2}, {"heat": 3}],
        "elements": [{"cold": 1}, {"toxin": 2}, {"heat": 3}],
    }})
    separate = Build(
        Upgrade({"stats": {"cold": 1, "elements": {"cold": 1}}}),
        Upgrade({"stats": {"toxin": 2, "elements": {"toxin": 2}}}),
        Upgrade({"stats": {"heat": 3, "elements": {"heat": 3}}}),
    )

    assert list(combined.stats.total.damage.data) == ["cold", "toxin", "heat"]
    assert list(combined.stats.total.elements) == ["cold", "toxin", "heat"]
    assert list(separate.stats.total.damage.data) == ["cold", "toxin", "heat"]
    assert list(separate.stats.total.elements) == ["cold", "toxin", "heat"]


def test_weapon_default_builds_are_independent():
    first = Primary()
    second = Primary()

    first.build.stats.total.damage.data["heat"] = 1

    assert first.build.stats.total.damage is not second.build.stats.total.damage
    assert second.build.stats.total.damage == Dist()
    assert first.stats.DEFAULT_BUILD.damage == Dist()


def test_upgrade_resolver_can_be_reused_with_different_contexts():
    upgrade = Upgrade({"stats": {"base_damage": {"value": 1, "when": "primary"}}})

    upgrade.stats.resolve(weapon=Data({"context": {"type": "primary"}}))
    assert upgrade.stats.total.base_damage == 1
    upgrade.stats.resolve(weapon=Data({"context": {"type": "melee"}}))
    assert "base_damage" not in upgrade.stats.total


def test_upgrade_resolver_exposes_resolved_effect_buckets():
    upgrade = Upgrade({"stats": {"base_damage": [1, {"value": 2, "when": "kill"}, {"value": 3, "when": "hit", "stacking": True}]}, "context": {"kill": True, "hit": 2}})

    upgrade.stats.resolve()

    assert upgrade.stats.static == {"base_damage": 1}
    assert upgrade.stats.conditional == {"base_damage": 2}
    assert upgrade.stats.stacking == {"base_damage": 6}
    assert upgrade.stats.total == {"base_damage": 9}
    assert not hasattr(upgrade.stats, "stacked")


def test_model_data_is_public():
    weapon = Primary()
    upgrade = Upgrade()
    build = Build(upgrade)
    damage = Dist({"impact": 1})

    assert all(hasattr(item, "data") for item in (weapon, upgrade, build, damage))
    assert weapon.data.context == {}
    assert upgrade.data.context == {}
    assert weapon.stats.weapon is weapon
    assert upgrade.stats.upgrade is upgrade
    assert build.stats.build is build
    assert weapon.format.weapon is weapon
    assert not any(hasattr(item, "data") for item in (weapon.stats, upgrade.stats, build.stats))
    assert not hasattr(weapon.format, "calculator")


def test_requested_calculator_api():
    weapon = Primary({"stats": {"damage": {"impact": 100, "slash": 50}, "crit_chance": 0.3, "crit_damage": 2.2, "status_chance": 0.3, "multishot": 6, "fire_rate": 3.0, "reload_speed": 1.5, "magazine_capacity": 20}, "context": {"name": "Example Weapon", "type": "shotgun", "trigger": "semi"}})
    mod1 = Upgrade({"stats": {"base_damage": 1.6, "multishot": [0.6, {"value": 1.2, "when": "kill"}], "status_chance": {"value": 0.3, "when": "headshot", "stacks": True}}, "context": {"name": "Mod 1", "type": "mod", "max_stacks": 6, "headshot": 5}})
    mod2 = Upgrade({"stats": {"damage": [{"heat": 1.2}, {"value": {"cold": 1.2}, "at_rank": 6}]}, "context": {"name": "Mod 2", "type": "mod", "max_rank": 10, "rank": 8}})
    build = Build(mod1, mod2)

    weapon.configure(build)

    assert weapon.data.context.name == "Example Weapon"
    assert weapon.build is build
    assert weapon.stats.weapon is weapon
    assert weapon.build.stats.total.damage == Dist({"heat": 1.2, "cold": 1.2})
    assert weapon.stats.base.magazine_capacity == 20
    assert isinstance(weapon.stats.average, Data)
    assert mod1.stats.static.multishot == 0.6
    assert mod1.stats.conditional.multishot == 1.2
    assert mod1.stats.stacking.status_chance == pytest.approx(1.5)
    assert mod1.stats.total.multishot == pytest.approx(1.8)
    assert mod2.stats.rank_locked.damage == Dist({"cold": 1.2})
    assert mod2.stats.total.damage == Dist({"heat": 1.2, "cold": 1.2})
    assert build.stats.total.damage == Dist({"heat": 1.2, "cold": 1.2})
    assert build.stats.conditional.multishot == 1.2
    resolved_build = weapon.build
    resolved_total = resolved_build.stats.total.copy()
    weapon.stats.recompute()
    assert weapon.build is resolved_build
    assert weapon.build.stats.total == resolved_total
    assert weapon.format.upgrades()
    assert weapon.build is resolved_build
    assert weapon.build.stats.total == resolved_total


def test_weapon_configure_supported_forms():
    first = Upgrade()
    second = Upgrade()
    weapon = Primary()
    assert weapon.configure(Build(first)) is weapon
    assert weapon.configure(first, second) is weapon
    assert weapon.configure() is weapon


def test_weapon_configure_rejects_mixed_arguments():
    with pytest.raises(TypeError, match="one Build or multiple Upgrade"):
        Primary().configure(Build(), Upgrade())


def test_void_is_a_damage_type():
    assert "void" in get_args(DamageType.__value__)
