DOT_MULTIPLIERS = (("slash", 2.1), ("heat", 3.0), ("toxin", 3.0), ("electricity", 3.0), ("gas", 3.0))
PHYSICAL_TYPES = ("impact", "puncture", "slash")
ELEMENTAL_TYPES = ("cold", "electricity", "heat", "toxin")
DAMAGE_TYPES = ("impact", "puncture", "slash", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "cold", "electricity", "heat", "toxin", "void", "tau", "true")
ELEMENTAL_COMBINATIONS = {frozenset(("cold", "heat")): "blast", frozenset(("electricity", "toxin")): "corrosive", frozenset(("heat", "toxin")): "gas", frozenset(("cold", "electricity")): "magnetic", frozenset(("electricity", "heat")): "radiation", frozenset(("cold", "toxin")): "viral"}
DAMAGE_TYPE_ORDER = {damage_type: index for index, damage_type in enumerate(DAMAGE_TYPES)}
