from typing import get_args

import pytest

from warframe_damage_calculator import Build, Data, Primary, Upgrade, arsenal
from warframe_damage_calculator.calculators.weapon_calculator import WeaponCalculator
from warframe_damage_calculator.models.dist import Dist
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
    calculator = WeaponCalculator(data)
    assert all(isinstance(calculator.base[field], Data) for field in stats)
    assert all(isinstance(data.stats[field], Data) for field in stats)
    assert isinstance(Upgrade({"stats": {"heat": 1}}).resolve().data.stats.damage, Data)


def test_dist_filters_accept_generators():
    damage = Dist({"impact": 1, "puncture": 2, "slash": 3})
    assert isinstance(damage.data, Data)
    assert damage.include(item for item in ("impact", "slash")) == Dist({"impact": 1, "slash": 3})
    assert damage.exclude(item for item in ("impact", "slash")) == Dist({"puncture": 2})


def test_build_aggregation():
    build = Build(
        Upgrade({"stats": {"base_damage": 0.5, "enabled": False}}),
        Upgrade({"stats": {"base_damage": 0.25, "enabled": True}}),
    )
    assert build.aggregate() == {"base_damage": 0.75, "enabled": True}


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
