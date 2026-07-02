from typing import TypedDict


class DistArgs(TypedDict, total=False):
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