from .distargs import DistArgs


DOT_MULTIPLIERS = (("slash", 2.1), ("heat", 3.0), ("toxin", 3.0), ("electricity", 3.0), ("gas", 3.0))
PHYSICAL_TYPES = ("impact", "puncture", "slash")
ELEMENTAL_TYPES = ("cold", "electricity", "heat", "toxin")
DAMAGE_TYPES = tuple(DistArgs.__annotations__)
ELEMENTAL_COMBINATIONS = {frozenset(("cold", "heat")): "blast", frozenset(("electricity", "toxin")): "corrosive", frozenset(("heat", "toxin")): "gas", frozenset(("cold", "electricity")): "magnetic", frozenset(("electricity", "heat")): "radiation", frozenset(("cold", "toxin")): "viral"}
DAMAGE_TYPE_ORDER = dict(zip(DAMAGE_TYPES, range(len(DAMAGE_TYPES))))