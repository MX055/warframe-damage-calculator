from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Iterable, Unpack
from types import MappingProxyType
from collections.abc import Mapping

from ..utils import PHYSICAL_TYPES, ELEMENTAL_TYPES, DAMAGE_TYPES, ELEMENTAL_COMBINATIONS, DAMAGE_TYPE_ORDER, DamageType
from ..fields import DamageField


@dataclass(frozen=True, init=False, slots=True)
class dist:
    dist: Mapping[DamageType, float]
    total_damage: float
    
    def __init__(self, **kwargs: Unpack[DamageField]) -> None:
        sorted_items = dict(sorted(kwargs.items(), key=lambda item: DAMAGE_TYPE_ORDER[item[0]]))
        object.__setattr__(self, "dist", MappingProxyType(sorted_items))
        object.__setattr__(self, 'total_damage', sum(sorted_items.values()))

    def __add__(self, other: dist) -> dist:
        if isinstance(other, dist):
            return dist(**{dt: self.get(dt) + other.get(dt) for dt in self.dist | other.dist})
        else: return NotImplemented
    
    def __radd__(self, other: int | float) -> dist:
        if other == 0: return self
        else: return NotImplemented
    
    def __mul__(self, other: int | float) -> dist:
        if isinstance(other, (int, float)):
            return dist(**{dt: d * other for dt, d in self})
        else: return NotImplemented
    
    def __rmul__(self, other: int | float) -> dist:
        if isinstance(other, (int, float)):
            return dist(**{dt: other * d for dt, d in self})
        else: return NotImplemented
    
    def __iter__(self) -> Iterator[tuple[DamageType, float]]:
        return iter(self.dist.items())
    
    def __hash__(self) -> int:
        return hash(tuple(self.dist.items()))

    def __str__(self) -> str:
        return ", ".join(f"{dt.upper()}: {d}" for dt, d in self)
    
    def __repr__(self) -> str:
        return f"dist({', '.join(f'{dt}={d}' for dt, d in self)})"
    
    def combine(self) -> dist:
        elements = list(self.include(ELEMENTAL_TYPES))
        combined: dict[str, float] = dict()
        for (dt1, d1), (dt2, d2) in zip(elements[::2], elements[1::2] + [("NONE", 0)]):
            key = ELEMENTAL_COMBINATIONS.get(frozenset((dt1, dt2)), dt1)
            combined[key] = d1 + d2
        return (self.exclude(ELEMENTAL_TYPES) + dist(**combined)).positive()
    
    def include(self, other: Iterable[DamageType]) -> dist:
        if not isinstance(other, Iterable):
            raise TypeError
        if any(dt not in DAMAGE_TYPES for dt in other):
            raise ValueError
        return dist(**{dt: d for dt, d in self if dt in other})

    def exclude(self, other: Iterable[DamageType]) -> dist:
        if not isinstance(other, Iterable):
            raise TypeError
        if any(dt not in DAMAGE_TYPES for dt in other):
            raise ValueError
        return dist(**{dt: d for dt, d in self if dt not in other})
    
    def positive(self) -> dist:
        return dist(**{dt: d for dt, d in self if d > 0})
    
    def get(self, dt: DamageType) -> float:
        if dt not in DAMAGE_TYPES:
            raise ValueError
        if not isinstance(dt, str):
            raise TypeError
        return self.dist.get(dt, 0) 
    
    def weight(self, dt: DamageType) -> float:
        if dt not in DAMAGE_TYPES:
            raise ValueError
        if not isinstance(dt, str):
            raise TypeError
        return 0.0 if self.total_damage == 0 else self.get(dt) / self.total_damage
    
    def apply(self, other: dist) -> dist:
        if not isinstance(other, dist):
            raise TypeError
        return dist(**{dt: self.get(dt) * (1 + other.get(dt)) if dt in PHYSICAL_TYPES else self.get(dt) + self.total_damage * other.get(dt) for dt in self.dist | other.dist})