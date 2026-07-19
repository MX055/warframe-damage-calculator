from collections.abc import MutableMapping
from typing import ClassVar, get_args

import pytest
import warframe_damage_calculator as package

from warframe_damage_calculator import Build, Melee, Primary, Secondary, Upgrade, arsenal
from warframe_damage_calculator.models.data import Data
from warframe_damage_calculator.models.fields import BuildContext, BuildData, MeleeContext, MeleeStats, PrimaryContext, PrimaryStats, RangedStats, ResolvedStat, SecondaryContext, SecondaryStats, SetupContext, UpgradeContext, UpgradeData, UpgradeStats, AverageStats, CalculatedStats, WeaponContext, WeaponData, WeaponStats
from warframe_damage_calculator.models.dist import Dist
from warframe_damage_calculator.models.weapon import Weapon
from warframe_damage_calculator.data.loader import WarframeDatabase
from warframe_damage_calculator.utils.types import DamageType


def test_loader_context_and_attributes():
    upgrade = arsenal.get("Serration", context={"rank": 2})
    assert upgrade.data.context.rank == 2
    assert upgrade.stats.total.base_damage == pytest.approx(0.45)
    assert arsenal.get("Serration", attribute="name") == "Serration"
    assert arsenal.get("Serration", attribute="base_damage") is not None

    beam = arsenal.get("Corinth Prime", context={"is_beam": True})
    regular = arsenal.get("Corinth Prime")
    assert beam.stats.effective.ammo_efficiency == pytest.approx(0.5)
    assert regular.data.context.is_beam is False
    assert regular.stats.effective.ammo_efficiency == 0


def test_loader_normalizes_legacy_rank_locked_effects():
    database = WarframeDatabase({}, {"mod": {"Legacy": {
        "context": {"max_rank": 5},
        "stats": {"base_damage": {"value": 1, "when": {"rank": 5}}},
    }}})

    upgrade = database.get("Legacy", context={"rank": 5})

    assert upgrade.data.stats.base_damage == {"value": 1, "at_rank": 5}
    assert upgrade.stats.rank_locked.base_damage == 1


def test_rifle_mods_are_tagged_as_sniper_compatible():
    serration = arsenal.get("Serration")
    assert "rifle" in serration.data.context.compatibility
    assert "sniper" in serration.data.context.compatibility


def test_default_distributions_are_independent():
    first_weapon = Primary()
    second_weapon = Primary()
    first_upgrade = Upgrade()
    second_upgrade = Upgrade()

    first_weapon.data.stats.damage.data["impact"] = 1
    first_upgrade.stats.total.damage.data["heat"] = 1

    assert first_weapon.data.stats.damage is not second_weapon.data.stats.damage
    assert second_weapon.data.stats.damage == Dist()
    assert first_upgrade.stats.total.damage is not second_upgrade.stats.total.damage
    assert second_upgrade.stats.total.damage == Dist()
    first_upgrade.data.context.compatibility.append("rifle")
    assert second_upgrade.data.context.compatibility == []


def test_data_copy_is_independent():
    original = Data({"nested": {"items": [{"value": 1}]}, "damage": {"impact": 2}})
    copied = original.copy()
    copied.nested["items"][0].value = 3
    copied.damage.impact = 4
    assert original.nested["items"][0].value == 1
    assert original.damage.impact == 2


def test_mutable_defaults_survive_reconstruction_and_mapping_unions():
    stats = RangedStats()
    assert "damage" not in stats
    stats.damage.data["impact"] = 10
    assert "damage" in stats

    reconstructed = RangedStats(stats)
    assert reconstructed.damage == Dist({"impact": 10})

    context = UpgradeContext()
    assert "compatibility" not in context
    context.compatibility.append("rifle")
    assert "compatibility" in context

    merged = context | {"name": "Serration"}
    reverse_merged = {"name": "Serration"} | context
    assert merged.compatibility == ["rifle"]
    assert reverse_merged.compatibility == ["rifle"]

    merged.compatibility.append("sniper")
    reverse_merged.compatibility.append("shotgun")
    assert context.compatibility == ["rifle"]

    suppressed = UpgradeContext()
    del suppressed.compatibility
    assert not hasattr(suppressed | {"name": "Mod"}, "compatibility")
    assert not hasattr({"name": "Mod"} | suppressed, "compatibility")


def test_with_defaults_returns_a_detached_snapshot():
    stats = RangedStats()
    values = stats.with_defaults()

    assert dict(stats) == {}
    values["damage"].data["impact"] = 10
    assert stats.damage == Dist()

    stats.crit_chance = 0.5
    stats.damage = {"slash": 20}
    del stats.forced_procs
    values = stats.with_defaults()

    assert values["crit_chance"] == 0.5
    assert values["damage"] == Dist({"slash": 20})
    assert "forced_procs" not in values

    values["damage"].data["slash"] = 30
    assert stats.damage == Dist({"slash": 20})


def test_data_repr_always_includes_defaults_without_promoting_them():
    stats = RangedStats()

    rendered = repr(stats)

    assert "'damage':" in rendered
    assert "'multishot': 1.0" in rendered
    assert dict(stats) == {}


def test_data_is_a_custom_mutable_mapping():
    data = Data({"nested": {"value": 1}})

    assert isinstance(data, MutableMapping)
    assert not isinstance(data, dict)
    assert isinstance(data.nested, Data)
    assert dict(data) == {"nested": {"value": 1}}


def test_inline_default_data_behavior():
    class Parent(Data):
        inherited: str = "parent"
        mutable: list[int] = []
        absent: int
        ignored: ClassVar[str] = "class value"
        _internal: str = "internal"

    class Child(Parent):
        inherited: str = "child"
        damage: Dist = Dist({"impact": 1})

    class Container(Data):
        entries: list[Child] = []

    first = Child({"inherited": "supplied"})
    second = Child()

    assert first.inherited == "supplied"
    assert second.inherited == "child"
    assert dict(first) == {"inherited": "supplied"}
    assert dict(second) == {}
    assert first.mutable == []
    assert "absent" not in first
    with pytest.raises(AttributeError):
        _ = first.absent
    assert "inherited" not in Child.__dict__
    assert Child.ignored == "class value"
    assert Child._internal == "internal"

    first.mutable.append(1)
    first.damage.data["impact"] = 2
    assert first.mutable == [1]
    assert first.damage == Dist({"impact": 2})
    assert second.mutable == []
    assert second.damage == Dist({"impact": 1})

    copied = first.copy()
    copied.mutable.append(2)
    copied.damage.data["impact"] = 3
    assert copied.mutable == [1, 2]
    assert copied.damage == Dist({"impact": 3})
    assert first.mutable == [1]
    assert first.damage == Dist({"impact": 2})
    assert dict(Child()) == {}

    existing = Child()
    container = Container({"entries": [{"inherited": "mapped"}, existing]})
    assert isinstance(container.entries[0], Child)
    assert container.entries[0].inherited == "mapped"
    assert container.entries[1] is existing

    context = UpgradeContext({"name": "Serration"})
    assert context.name == "Serration"
    assert context.category == "Upgrade"
    assert context.compatibility == []
    assert context.max_rank is None
    assert "rank" not in context
    assert context.rank is None

    resolved = ResolvedStat({"base_damage": 1})
    other = ResolvedStat()
    assert dict(resolved) == {"base_damage": 1}
    assert dict(other) == {}
    assert resolved.base_damage == 1
    assert resolved.crit_chance == 0.0
    assert resolved.fire_rate_lock is False
    assert resolved.multishot_lock is False
    assert isinstance(resolved.damage, Dist)
    assert isinstance(resolved.elements, Data)
    assert resolved.damage is not other.damage
    assert resolved.elements is not other.elements
    assert all(hasattr(other, field) for field in ResolvedStat._fields)

    dense = second.with_defaults()
    assert dense["inherited"] == "child"
    assert dense["mutable"] == []
    assert "absent" not in dense


def test_typed_data_subclasses_preserve_nested_and_copy_types():
    weapon = Primary({"stats": {"damage": {"impact": 1}, "crit_chance": 0.3}, "context": {"is_beam": True}})
    upgrade = Upgrade({"stats": {"base_damage": 1}, "context": {"rank": 2}})
    build = Build(upgrade)

    assert isinstance(weapon.data, WeaponData)
    assert isinstance(weapon.data.stats, WeaponStats)
    assert isinstance(weapon.data.stats.damage, Dist)
    assert weapon.data.stats.multishot == 1
    assert isinstance(weapon.data.context, WeaponContext)
    assert isinstance(weapon.stats.base, CalculatedStats)
    assert isinstance(weapon.stats.modded, CalculatedStats)
    assert isinstance(weapon.stats.effective, CalculatedStats)
    assert isinstance(weapon.stats.average, AverageStats)
    assert isinstance(upgrade.data, UpgradeData)
    assert isinstance(upgrade.data.stats, UpgradeStats)
    assert isinstance(upgrade.data.context, UpgradeContext)
    assert isinstance(upgrade.stats.total, ResolvedStat)
    assert isinstance(upgrade.stats.static, ResolvedStat)
    assert upgrade.stats.total.crit_chance == 0
    assert isinstance(build.data, BuildData)
    assert isinstance(build.data.context, BuildContext)
    assert isinstance(build.data.upgrades[0], UpgradeData)
    assert isinstance(build.stats.total, ResolvedStat)
    assert isinstance(build.stats.static, ResolvedStat)
    assert build.stats.total.crit_chance == 0

    weapon.data.stats.damage = {"impact": 2}
    upgrade.stats.total.damage = {"heat": 1}
    assert weapon.data.stats.damage == Dist({"impact": 2})
    assert upgrade.stats.total.damage == Dist({"heat": 1})

    assert isinstance(weapon.data.copy(), WeaponData)
    assert isinstance(weapon.data | {"context": {"is_beam": False}}, WeaponData)
    assert isinstance({"context": {"is_beam": False}} | weapon.data, WeaponData)
    assert isinstance(weapon.data.copy().stats, WeaponStats)


def test_weapon_input_defaults_and_category_types():
    primary = Primary({"stats": {"crit_chance": 0.4}, "context": {"is_beam": True}})
    secondary = Secondary()
    melee = Melee()

    assert type(primary.data.stats) is PrimaryStats
    assert type(primary.data.context) is PrimaryContext
    assert type(secondary.data.stats) is SecondaryStats
    assert type(secondary.data.context) is SecondaryContext
    assert type(melee.data.stats) is MeleeStats
    assert type(melee.data.context) is MeleeContext
    assert primary.data.stats.crit_chance == 0.4
    assert primary.data.context.is_beam is True
    assert primary.data.stats.multishot == 1
    assert primary.data.stats.fire_rate == 0.05
    assert primary.data.stats.weakpoint_damage == 3
    assert melee.data.stats.attack_speed == 1

    calculator_only = {"multiplicative_base_damage", "base_damage", "faction_damage", "flat_crit_chance", "multiplicative_crit_chance", "flat_crit_damage", "status_damage", "multiplicative_fire_rate", "ammo_efficiency", "multiplicative_weakpoint_crit_chance", "weakpoint_crit_chance", "internal_bleeding", "hunter_munitions", "primed_chamber", "vigilante_bonus", "secondary_enervate", "secondary_encumber", "melee_doughty", "melee_duplicate"}
    assert calculator_only.isdisjoint(primary.data.stats)
    assert calculator_only.isdisjoint(melee.data.stats)


def test_dist_is_not_exported_from_package_root():
    assert not hasattr(package, "Dist")


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
        Upgrade({"stats": {"base_damage": 0.5, "fire_rate_lock": False}}),
        Upgrade({"stats": {"base_damage": 0.25, "fire_rate_lock": True}}),
    )
    assert build.stats.total.base_damage == 0.75
    assert build.stats.total.fire_rate_lock is True


def test_build_context_tracks_upgrade_mutations():
    build = Build()
    pressure = Upgrade({"context": {"name": "Sacrificial Pressure"}})
    steel = Upgrade({"context": {"name": "Sacrificial Steel"}})

    assert build.data.context.equipped == []

    build.data.upgrades.append(pressure.data)
    build.data.upgrades.append(steel.data)
    build.stats.resolve()
    assert build.data.context.equipped == ["sacrificial pressure", "sacrificial steel"]

    build.data.upgrades.pop()
    build.stats.resolve()
    assert build.data.context.equipped == ["sacrificial pressure"]


def test_upgrade_effect_can_require_an_equipped_upgrade():
    bonus = Upgrade({
        "context": {"name": "Bonus"},
        "stats": {"base_damage": [1, {"value": 2, "when_equipped": "Partner"}]},
    })
    partner = Upgrade({"context": {"name": "Partner"}})

    alone = Build(bonus)
    together = Build(bonus, partner)

    bonus.stats.resolve(build=together)
    assert bonus.stats.modular.base_damage == 2
    assert alone.stats.total.base_damage == 1
    assert together.stats.static.base_damage == 1
    assert together.stats.conditional == {}
    assert together.stats.modular.base_damage == 2
    assert together.stats.total.base_damage == 3

    pressure = arsenal.get("Sacrificial Pressure")
    steel = arsenal.get("Sacrificial Steel")
    assert Build(steel).stats.total.crit_chance == 2.2
    sacrificial = Build(pressure, steel)
    assert sacrificial.stats.total.base_damage == 1.375
    assert sacrificial.stats.total.crit_chance == 2.75


def test_automatic_special_mechanics_are_static_upgrade_stats():
    encumber = arsenal.get("Secondary Encumber")
    enervate = arsenal.get("Secondary Enervate")
    duplicate = arsenal.get("Melee Duplicate")
    doughty = arsenal.get("Melee Doughty")
    bleeding = arsenal.get("Internal Bleeding")
    hemorrhage = arsenal.get("Hemorrhage")

    assert encumber.stats.static.secondary_encumber == 0.24
    assert encumber.stats.conditional == {}
    assert enervate.data.stats == {"secondary_enervate": 6}
    assert enervate.stats.static.secondary_enervate == 6
    assert enervate.stats.conditional == {}
    assert duplicate.stats.static.melee_duplicate == 1
    assert duplicate.stats.conditional == {}
    assert doughty.stats.static.melee_doughty == 2
    assert doughty.stats.conditional == {}
    assert bleeding.stats.static.internal_bleeding == 0.35
    assert bleeding.stats.conditional == {}
    assert hemorrhage.stats.static.internal_bleeding == 0.35
    assert hemorrhage.stats.conditional == {}


def test_build_resolver_returns_none():
    build = Build(Upgrade({"stats": {"base_damage": 0.5}}))

    resolved = build.stats.resolve()

    assert resolved is None
    assert build.stats.total.base_damage == 0.5


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
    assert first.build.stats.total.base_damage == 0


def test_upgrade_resolver_can_be_reused_with_different_contexts():
    upgrade = Upgrade({"stats": {"base_damage": {"value": 1, "when": "primary"}}, "context": {"category": "mod"}})

    primary = Data({"context": {"category": "primary", "type": "rifle"}})
    context = upgrade.stats._context(primary, Data({"upgrades": []}))
    assert isinstance(context, SetupContext)
    assert isinstance(context.weapon, WeaponContext)
    assert isinstance(context.build, BuildContext)
    assert isinstance(context.upgrade, UpgradeContext)
    assert context.weapon.category == "primary"
    assert context.upgrade.category == "mod"
    assert not ({"primary", "rifle", "bow", "shotgun", "sniper", "secondary", "pistol", "melee"} & set(context))

    upgrade.stats.resolve(weapon=primary)
    assert upgrade.stats.total.base_damage == 1
    upgrade.stats.resolve(weapon=Data({"context": {"type": "melee"}}))
    assert upgrade.stats.total.base_damage == 0


def test_upgrade_resolver_returns_none():
    upgrade = Upgrade({"stats": {"base_damage": 1}, "context": {"rank": 2}})

    resolved = upgrade.stats.resolve()

    assert resolved is None
    assert upgrade.stats.total.base_damage == 1


def test_upgrade_resolver_exposes_resolved_effect_buckets():
    upgrade = Upgrade({"stats": {"base_damage": [1, {"value": 2, "when": "kill"}, {"value": 3, "stacks_on": "hit"}]}, "context": {"kill": True, "hit": 2}})

    upgrade.stats.resolve()

    assert upgrade.stats.static == {"base_damage": 1}
    assert upgrade.stats.conditional == {"base_damage": 2}
    assert upgrade.stats.modular == {}
    assert upgrade.stats.stacking == {"base_damage": 6}
    assert upgrade.stats.total.base_damage == 9
    assert not hasattr(upgrade.stats, "stacked")


def test_model_data_is_public():
    weapon = Primary()
    upgrade = Upgrade()
    build = Build(upgrade)
    damage = Dist({"impact": 1})

    assert all(hasattr(item, "data") for item in (weapon, upgrade, build, damage))
    assert weapon.data.context == PrimaryContext()
    assert upgrade.data.context == UpgradeContext()
    assert weapon.stats.weapon is weapon
    assert upgrade.stats.upgrade is upgrade
    assert build.stats.build is build
    assert weapon.format.weapon is weapon
    assert not any(hasattr(item, "data") for item in (weapon.stats, upgrade.stats, build.stats))
    assert not hasattr(weapon.format, "calculator")


def test_requested_calculator_api():
    weapon = Primary({"stats": {"damage": {"impact": 100, "slash": 50}, "crit_chance": 0.3, "crit_damage": 2.2, "status_chance": 0.3, "multishot": 6, "fire_rate": 3.0, "reload_speed": 1.5, "magazine_capacity": 20}, "context": {"name": "Example Weapon", "type": "shotgun", "trigger": "semi"}})
    mod1 = Upgrade({"stats": {"base_damage": 1.6, "multishot": [0.6, {"value": 1.2, "when": "kill"}], "status_chance": {"value": 0.3, "stacks_on": "headshot"}}, "context": {"name": "Mod 1", "type": "mod", "max_stacks": 6, "headshot": 5}})
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
