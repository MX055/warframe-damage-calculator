from collections.abc import Mapping
from typing import Self

from ..calculators.weapon_calculator import WeaponCalculator
from ..formatters.weapon_formatter import WeaponFormatter
from ..utils.types import JsonValue
from .build import Build
from .fields import WeaponData, WeaponStats


class Weapon:
    data_type = WeaponData
    mode_stats_type = WeaponStats
    calculator_type = WeaponCalculator
    formatter_type = WeaponFormatter

    def __init__(self, data: Mapping[str, JsonValue] | None = None) -> None:
        self.data = self.data_type(data or {})
        self.mode = next(iter(self.data.entry.attacks.values()))
        self.build = Build()
        self.evolutions: dict[str, int] = {}
        self.stats = self.calculator_type(self)
        self.format = self.formatter_type(self)

    def configure(self, build: Build | None = None) -> Self:
        build = Build() if build is None else build
        if not isinstance(build, Build):
            raise TypeError("configure() requires a Build")
        self.build = build.copy()
        self.stats.recompute()
        return self

    def set_mode(self, name: str) -> Self:
        key = "_".join(name.casefold().replace("-", " ").split())
        match = self.data.entry.attacks.get(key)
        if match is None:
            available = ", ".join(identifier.replace("_", " ").title() for identifier in self.data.entry.attacks)
            raise ValueError(f"Unknown attack {name!r} for {self.data.name!r}. Available attacks: {available}")
        self.mode = match
        self.stats.recompute()
        return self

    def set_evolutions(self, **selections: int) -> Self:
        for evolution, perk in selections.items():
            tier_id = evolution.removeprefix("evolution_")
            tier = self.data.entry.evolutions.get(tier_id)
            if tier is None:
                available = ", ".join(f"evolution_{tier}" for tier in self.data.entry.evolutions)
                raise ValueError(f"Unknown evolution {evolution!r}. Available evolutions: {available}")
            if str(perk) not in tier:
                available = ", ".join(tier)
                raise ValueError(f"Invalid perk {perk} for {evolution}. Available perks: {available}")
        self.evolutions.update(selections)
        self.stats.recompute()
        return self
