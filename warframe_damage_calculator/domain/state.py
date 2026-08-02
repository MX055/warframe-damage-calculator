from __future__ import annotations

from collections.abc import Mapping
from math import floor
from typing import Self


ALLOWED_STATE_FIELDS = frozenset({"combo_multiplier", "stance_combo", "ability_strength"})


def combo_multiplier_from_hits(hits: float, max_combo: int = 12) -> int:
    return max(1, min(int(max_combo), floor(float(hits) / 20) + 1))


class State(dict[str, object]):
    """Calculation state overrides shared by calculators and optimizers."""

    def __init__(self, /, *, combo_multiplier: int | None = None, stance_combo: str | None = None, ability_strength: float | None = None) -> None:
        super().__init__()
        if combo_multiplier is not None: self["combo_multiplier"] = int(combo_multiplier)
        if stance_combo is not None: self["stance_combo"] = str(stance_combo)
        if ability_strength is not None: self["ability_strength"] = float(ability_strength)

    @classmethod
    def _from_values(cls, values: Mapping[str, object] | None = None) -> Self:
        payload = dict(values or {})
        unknown = set(payload) - ALLOWED_STATE_FIELDS
        if unknown: raise TypeError(f"unknown calculation state fields: {', '.join(sorted(unknown))}")
        state = cls()
        state.update(payload)
        return state

    def __getattr__(self, name: str) -> object:
        try: return self[name]
        except KeyError: raise AttributeError(name) from None

    def copy(self) -> State:
        return State._from_values(self)
