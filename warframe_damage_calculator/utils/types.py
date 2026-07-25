from collections.abc import Mapping
from typing import Literal, Any


type DamageType = Literal["impact", "puncture", "slash", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "cold", "electricity", "heat", "toxin", "void", "tau", "true"]
type EffectMode = Literal["proportional", "base", "flat"]
type ContributionTarget = Literal["flat_dph", "flat_weakpoint_dph", "flat_dps", "flat_weakpoint_dps", "flat_dotph", "flat_weakpoint_dotph", "flat_dotps", "flat_weakpoint_dotps", "total_dph", "total_weakpoint_dph", "total_dps", "total_weakpoint_dps"]
type Number = int | float
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | Mapping[str, JsonValue] | list[JsonValue]
type DataValue = Any
