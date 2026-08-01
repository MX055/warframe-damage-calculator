from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Self


PHYSICAL_TYPES = frozenset({"impact", "puncture", "slash"})
BASE_ELEMENT_TYPES = frozenset({"heat", "cold", "electricity", "toxin"})
ELEMENTAL_COMBINATIONS = {
    frozenset({"heat", "cold"}): "blast",
    frozenset({"heat", "electricity"}): "radiation",
    frozenset({"heat", "toxin"}): "gas",
    frozenset({"cold", "electricity"}): "magnetic",
    frozenset({"cold", "toxin"}): "viral",
    frozenset({"electricity", "toxin"}): "corrosive",
}


class Dist(Mapping[str, float]):
    __slots__ = ("_amounts", "_total")

    def __init__(self, values: Mapping[str, int | float] | None = None, /, **amounts: int | float) -> None:
        merged = dict(values or {})
        merged.update(amounts)
        self._amounts = {str(kind).lower(): float(amount) for kind, amount in merged.items() if amount}
        self._total = sum(self._amounts.values())

    def __getitem__(self, kind: str) -> float:
        return self._amounts[kind]

    def __iter__(self) -> Iterator[str]:
        return iter(self._amounts)

    def __len__(self) -> int:
        return len(self._amounts)

    def __repr__(self) -> str:
        values = ", ".join(f"{kind}={amount!r}" for kind, amount in self.items())
        return f"Dist({values})"

    def __add__(self, other: Self) -> Self:
        kinds = [*self, *(kind for kind in other if kind not in self)]
        return type(self)({kind: self.get(kind, 0) + other.get(kind, 0) for kind in kinds})

    def __radd__(self, other: int) -> Self:
        return self if other == 0 else NotImplemented

    def __mul__(self, multiplier: int | float) -> Self:
        return type(self)({kind: amount * multiplier for kind, amount in self.items()})

    __rmul__ = __mul__

    def __truediv__(self, divisor: int | float) -> Self:
        return self * (1 / divisor)

    @property
    def total(self) -> float:
        return self._total

    def weight(self, kind: str) -> float:
        return self._amounts.get(kind, 0.0) / self._total if self._total else 0.0

    def include(self, kinds: Iterable[str]) -> Self:
        included = set(kinds)
        return type(self)({kind: amount for kind, amount in self.items() if kind in included})

    def exclude(self, kinds: Iterable[str]) -> Self:
        excluded = set(kinds)
        return type(self)({kind: amount for kind, amount in self.items() if kind not in excluded})

    def combine_elements(self) -> Self:
        elements = list(self.include(BASE_ELEMENT_TYPES).items())
        combined: dict[str, float] = {}
        for index in range(0, len(elements), 2):
            first, first_amount = elements[index]
            if index + 1 == len(elements):
                combined[first] = combined.get(first, 0) + first_amount
                continue
            second, second_amount = elements[index + 1]
            result = ELEMENTAL_COMBINATIONS[frozenset({first, second})]
            combined[result] = combined.get(result, 0) + first_amount + second_amount
        return self.exclude(BASE_ELEMENT_TYPES) + type(self)(combined)

    def apply_modifiers(self, modifiers: Mapping[str, int | float]) -> Self:
        kinds = [*self, *(kind for kind in modifiers if kind not in self)]
        total = self._total
        modified = {
            kind: self.get(kind, 0) * (1 + modifiers.get(kind, 0)) if kind in PHYSICAL_TYPES else self.get(kind, 0) + total * modifiers.get(kind, 0)
            for kind in kinds
        }
        return type(self)(modified).combine_elements()
