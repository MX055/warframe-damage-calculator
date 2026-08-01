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
_ELEMENTAL_PAIR = {
    ("heat", "cold"): "blast", ("cold", "heat"): "blast",
    ("heat", "electricity"): "radiation", ("electricity", "heat"): "radiation",
    ("heat", "toxin"): "gas", ("toxin", "heat"): "gas",
    ("cold", "electricity"): "magnetic", ("electricity", "cold"): "magnetic",
    ("cold", "toxin"): "viral", ("toxin", "cold"): "viral",
    ("electricity", "toxin"): "corrosive", ("toxin", "electricity"): "corrosive",
}


class Dist(Mapping[str, float]):
    __slots__ = ("_amounts", "_total")

    @classmethod
    def _from_amounts(cls, amounts: dict[str, float]) -> Self:
        result = cls.__new__(cls)
        result._amounts = {kind: amount for kind, amount in amounts.items() if amount}
        result._total = sum(result._amounts.values())
        return result

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
        amounts = dict(self._amounts)
        for kind, amount in other._amounts.items(): amounts[kind] = amounts.get(kind, 0.0) + amount
        return type(self)._from_amounts(amounts)

    def __radd__(self, other: int) -> Self:
        return self if other == 0 else NotImplemented

    def __mul__(self, multiplier: int | float) -> Self:
        value = float(multiplier)
        return type(self)._from_amounts({kind: amount * value for kind, amount in self._amounts.items()})

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
        return type(self)._from_amounts({kind: amount for kind, amount in self._amounts.items() if kind in included})

    def exclude(self, kinds: Iterable[str]) -> Self:
        excluded = set(kinds)
        return type(self)._from_amounts({kind: amount for kind, amount in self._amounts.items() if kind not in excluded})

    def combine_elements(self) -> Self:
        source = self._amounts
        elements = [(kind, amount) for kind, amount in source.items() if kind in BASE_ELEMENT_TYPES]
        if not elements: return self
        combined = {kind: amount for kind, amount in source.items() if kind not in BASE_ELEMENT_TYPES}
        for index in range(0, len(elements), 2):
            first, first_amount = elements[index]
            if index + 1 == len(elements):
                combined[first] = combined.get(first, 0.0) + first_amount
                continue
            second, second_amount = elements[index + 1]
            result = _ELEMENTAL_PAIR[(first, second)]
            combined[result] = combined.get(result, 0.0) + first_amount + second_amount
        return type(self)._from_amounts(combined)

    def apply_modifiers(self, modifiers: Mapping[str, int | float]) -> Self:
        source = self._amounts
        total = self._total
        modified: dict[str, float] = {}
        for kind, amount in source.items():
            modifier = modifiers.get(kind, 0)
            modified[kind] = amount * (1 + modifier) if kind in PHYSICAL_TYPES else amount + total * modifier
        for kind, modifier in modifiers.items():
            if kind not in source: modified[kind] = total * modifier
        return type(self)._from_amounts(modified).combine_elements()
