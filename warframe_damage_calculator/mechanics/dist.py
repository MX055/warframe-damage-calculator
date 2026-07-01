from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Iterable
from types import MappingProxyType

from .constants import ELEMENTAL_COMBINATIONS, ELEMENTAL_TYPES, DAMAGE_TYPE_ORDER, PHYSICAL_TYPES


@dataclass(frozen=True, init=False)
class dist:
    _dist: dict[str, float] = field(default_factory=dict)
    _total_damage: float = 0.0
    
    def __init__(self, **kwargs: float):
        sorted_items = dict(sorted(kwargs.items(), key=lambda item: DAMAGE_TYPE_ORDER.get(item[0], float("inf"))))
        object.__setattr__(self, '_dist', sorted_items)
        object.__setattr__(self, '_total_damage', sum(sorted_items.values()))

    def __add__(self, other: dist) -> dist:
        return dist(**{dt: self.get(dt) + other.get(dt) for dt in self.dist | other.dist})
    
    def __radd__(self, other: int | float) -> dist:
        if other == 0: return self
        else: return NotImplemented
    
    def __mul__(self, other: int | float) -> dist:
        return dist(**{dt: d * other for dt, d in self})
    
    def __rmul__(self, other: int | float) -> dist:
        return dist(**{dt: other * d for dt, d in self})
    
    def __iter__(self) -> Iterator[tuple[str, float]]:
        return iter(self.dist.items())
    
    def __hash__(self) -> int:
        return hash(tuple(sorted(self.dist.items())))

    def __str__(self) -> str:
        return ", ".join(f"{dt.upper()}: {d}" for dt, d in self)
    
    def __repr__(self) -> str:
        return f"dist({', '.join(f'{dt}={d}' for dt, d in self)})"
    
    @property
    def dist(self) -> dict[str, float]:
        return MappingProxyType(self._dist)
    
    @property
    def total_damage(self) -> float:
        return self._total_damage
    
    def get(self, dt: str) -> float:
        return self.dist.get(dt, 0)
    
    def combine(self) -> dist:
        elements = list(self.include(ELEMENTAL_TYPES))
        combined: dict[str, float] = dict()
        for (dt1, d1), (dt2, d2) in zip(elements[::2], elements[1::2] + [("NONE", 0)]):
            key = ELEMENTAL_COMBINATIONS.get(tuple(sorted((dt1, dt2))), dt1)
            combined[key] = d1 + d2
        return (self.exclude(ELEMENTAL_TYPES) + dist(**combined)).positive()
    
    def include(self, other: Iterable[str]) -> dist:
        return dist(**{dt: d for dt, d in self if dt in other})

    def exclude(self, other: Iterable[str]) -> dist:
        return dist(**{dt: d for dt, d in self if dt not in other})
    
    def positive(self) -> dist:
        return dist(**{dt: d for dt, d in self if d > 0})
    
    def weight(self, dt: str) -> float:
        return 0.0 if self.total_damage == 0 else self.get(dt) / self.total_damage
    
    def apply(self, other: dist) -> dist:
        return dist(**{dt: self.get(dt) * (1 + other.get(dt)) if dt in PHYSICAL_TYPES else self.get(dt) + self.total_damage * other.get(dt) for dt in self.dist | other.dist})