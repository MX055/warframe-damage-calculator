from typing import TypedDict


class DamageFields(TypedDict, total=False):
	"""Keyword fields for creating a damage distribution.

	Each optional field is a supported damage type, such as ``slash`` or
	``heat``, and its value is the amount assigned to that type.

	Callers only need to provide the damage types they want to include. Missing
	types are treated as zero by ``dist.get``.

	Used anywhere the calculator needs values grouped by damage type, including
	base damage, elemental bonuses, and forced status procs.
	"""
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