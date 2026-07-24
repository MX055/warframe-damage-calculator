DOT_MULTIPLIERS = (("slash", 0.35), ("heat", 0.5), ("toxin", 0.5), ("electricity", 0.5), ("gas", 0.5))
PHYSICAL_TYPES = ("impact", "puncture", "slash")
ELEMENTAL_TYPES = ("cold", "electricity", "heat", "toxin")
DAMAGE_TYPES = ("impact", "puncture", "slash", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "cold", "electricity", "heat", "toxin", "void", "tau", "true")
ELEMENTAL_COMBINATIONS = {frozenset(("cold", "heat")): "blast", frozenset(("electricity", "toxin")): "corrosive", frozenset(("heat", "toxin")): "gas", frozenset(("cold", "electricity")): "magnetic", frozenset(("electricity", "heat")): "radiation", frozenset(("cold", "toxin")): "viral"}
DAMAGE_TYPE_ORDER = {damage_type: index for index, damage_type in enumerate(DAMAGE_TYPES)}
EFFECT_MODES = ("additive", "multiplicative", "base", "flat")
