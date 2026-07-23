from collections.abc import Mapping

from ..models.data import Data
from ..utils.types import JsonValue, Number
from .weapon_input import AttackStats


class Attack(Data):
    name: str = ""
    trigger: str | None = None
    delivery: str | None = None
    aoe: bool = False
    children: list[str] = []
    stats: AttackStats = {}


class Attacks(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, Attack):
            value = Attack(value)
        if isinstance(value, Attack) and not value.name:
            value.name = key
        super().__setitem__(key, value)


class Evolution(Data):
    pass


class Evolutions(Data):
    def __setitem__(self, key: str, value: JsonValue) -> None:
        if isinstance(value, Mapping) and not isinstance(value, Evolution):
            value = Evolution(value)
        super().__setitem__(key, value)


class WeaponData(Data):
    name: str = ""
    type: str | None = None
    subtype: str | None = None
    disposition: Number = 0.0
    ammo: Data = {}
    attacks: Attacks = Attacks()
    evolutions: Evolutions = Evolutions()


class RangedData(WeaponData):
    pass


class MeleeData(WeaponData):
    pass


class PrimaryData(RangedData):
    pass


class SecondaryData(RangedData):
    pass
