from typing import TypedDict, Literal, get_args


class DamageFields(TypedDict, total=False):
	impact: float
	puncture: float
	slash: float
	blast: float
	corrosive: float
	gas: float
	magnetic: float
	radiation: float
	viral: float
	cold: float
	electricity: float
	heat: float
	toxin: float
	void: float


DamageType = Literal[
    "impact",
    "puncture",
    "slash",
    "blast",
    "corrosive",
    "gas",
    "magnetic",
    "radiation",
    "viral",
    "cold",
    "electricity",
    "heat",
    "toxin",
	"void",
]

DOT_MULTIPLIERS = (("slash", 2.1), ("heat", 3.0), ("toxin", 3.0), ("electricity", 3.0), ("gas", 3.0))
PHYSICAL_TYPES = ("impact", "puncture", "slash")
ELEMENTAL_TYPES = ("cold", "electricity", "heat", "toxin")
DAMAGE_TYPES = get_args(DamageType)
ELEMENTAL_COMBINATIONS = {frozenset(("cold", "heat")): "blast", frozenset(("electricity", "toxin")): "corrosive", frozenset(("heat", "toxin")): "gas", frozenset(("cold", "electricity")): "magnetic", frozenset(("electricity", "heat")): "radiation", frozenset(("cold", "toxin")): "viral"}
DAMAGE_TYPE_ORDER = {dt: idx for idx, dt in enumerate(get_args(DamageType))}