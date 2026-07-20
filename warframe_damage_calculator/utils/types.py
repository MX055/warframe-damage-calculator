from collections.abc import Mapping
from typing import Literal, Any


type DamageType = Literal["impact", "puncture", "slash", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "cold", "electricity", "heat", "toxin", "void", "tau", "true"]
type Number = int | float
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | Mapping[str, JsonValue] | list[JsonValue]
type DataValue = Any
