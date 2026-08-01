from ..domain.effects import Scalar
from ..domain.upgrades import ResolvedEffect


def automatic_values(effect: ResolvedEffect, key: str) -> tuple[Scalar, ...]:
    value = effect.automatic.get(key.lower())
    if value is None: return ()
    return tuple(value) if isinstance(value, list) else (value,)


def automatic_value(effect: ResolvedEffect, key: str, default: Scalar | None = None) -> Scalar | None:
    values = automatic_values(effect, key)
    return values[0] if values else default


def effects_for(effects: list[ResolvedEffect], *, stat: str, event: str | None = None) -> list[ResolvedEffect]:
    return [effect for effect in effects if effect.stat == stat and (event is None or automatic_value(effect, "on") == event)]
