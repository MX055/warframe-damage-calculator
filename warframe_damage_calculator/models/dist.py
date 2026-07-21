from collections.abc import Iterable, Iterator, Mapping
from typing import Self

from ..utils.constants import DAMAGE_TYPE_ORDER, ELEMENTAL_COMBINATIONS, ELEMENTAL_TYPES, PHYSICAL_TYPES
from ..utils.types import DamageType, Number
from .data import Data


class DistData(Data):
    impact: Number
    puncture: Number
    slash: Number
    blast: Number
    corrosive: Number
    gas: Number
    magnetic: Number
    radiation: Number
    viral: Number
    cold: Number
    electricity: Number
    heat: Number
    toxin: Number
    void: Number
    tau: Number
    true: Number


class Dist:
    def __init__(self, data: Mapping[DamageType, Number] | None = None) -> None:
        self.data = DistData(data or {})

    def __iter__(self) -> Iterator[tuple[DamageType, Number]]:
        return iter(self.data.items())

    def __repr__(self) -> str:
        return f"dist({self.data!r})"

    def __str__(self) -> str:
        return ", ".join(f"{damage_type}: {value}" for damage_type, value in self)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Dist) and self.data == other.data

    def __add__(self, other: Self) -> Self:
        return Dist({damage_type: self.get(damage_type) + other.get(damage_type) for damage_type in self.data | other.data})

    def __radd__(self, other: int) -> Self:
        return self if other == 0 else NotImplemented

    def __mul__(self, multiplier: Number) -> Self:
        return Dist({damage_type: value * multiplier for damage_type, value in self})

    __rmul__ = __mul__

    def get(self, damage_type: DamageType, default: Number = 0.0) -> Number:
        return self.data.get(damage_type, default)

    def total_damage(self) -> Number:
        return sum(self.data.values())

    def weight(self, damage_type: DamageType) -> Number:
        return self.get(damage_type) / (self.total_damage() or 1)

    def include(self, damage_types: Iterable[DamageType]) -> Self:
        included = set(damage_types)
        return Dist({damage_type: value for damage_type, value in self if damage_type in included})

    def exclude(self, damage_types: Iterable[DamageType]) -> Self:
        excluded = set(damage_types)
        return Dist({damage_type: value for damage_type, value in self if damage_type not in excluded})

    def positive(self) -> Self:
        return Dist({damage_type: value for damage_type, value in self if value > 0})

    def apply(self, other: Self) -> Self:
        total = self.total_damage()
        return Dist({
            damage_type: self.get(damage_type) * (1 + other.get(damage_type))
            if damage_type in PHYSICAL_TYPES
            else self.get(damage_type) + total * other.get(damage_type)
            for damage_type in self.data | other.data
        })

    def combine(self) -> Self:
        elements = list(self.include(ELEMENTAL_TYPES))
        combined: dict[DamageType, Number] = {}
        pairs = zip(elements[::2], elements[1::2] + [(None, 0.0)])

        for (first_type, first_value), (second_type, second_value) in pairs:
            result_type = ELEMENTAL_COMBINATIONS.get(frozenset((first_type, second_type)), first_type)
            combined[result_type] = first_value + second_value

        return (self.exclude(ELEMENTAL_TYPES) + Dist(combined)).positive()

    def sorted(self) -> Self:
        return Dist(dict(sorted(self.data.items(), key=lambda item: DAMAGE_TYPE_ORDER[item[0]])))
