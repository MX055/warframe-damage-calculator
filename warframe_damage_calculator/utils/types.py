from typing import Any, Literal

type Stat = str
type Context = str
type Key = str

type Number = int | float
type Value = Any
type Json = dict[str, Any]
type DamageType = Literal["impact", "puncture", "slash", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "cold", "electricity", "heat", "toxin"]
