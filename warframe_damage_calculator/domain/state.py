from __future__ import annotations

from collections.abc import Mapping


class State(dict[str, object]):
    """Calculation state overrides shared by calculators and optimizers."""

    def __init__(self, values: Mapping[str, object] | None = None, /, *, combo: int | None = None, stance_combo: str | None = None, ability_strength: float | None = None, **conditions: object) -> None:
        super().__init__(values or {})
        if combo is not None: self["combo"] = combo
        if stance_combo is not None: self["stance_combo"] = stance_combo
        if ability_strength is not None: self["ability_strength"] = ability_strength
        self.update(conditions)

    def __getattr__(self, name: str) -> object:
        try: return self[name]
        except KeyError: raise AttributeError(name) from None

    def copy(self) -> State:
        return State(self)
