from collections.abc import Mapping

from ..core.data import Data
from ..utils.types import JsonValue, Number
from .evolution import Evolutions
from .weapon_input import AttackStats


class Attack(Data):
    name: str = ""
    trigger: str | None = None
    delivery: str | None = None
    form: str = "normal"
    category: str = "normal"
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


class WeaponData(Data):
    name: str = ""
    type: str | None = None
    subtype: str | None = None
    disposition: Number = 0.0
    ammo: Data = {}
    attacks: Attacks = Attacks()
    evolutions: Evolutions = Evolutions()

    @property
    def runtime(self) -> Data:
        runtime = getattr(self, "_runtime", None)
        if runtime is None:
            runtime = Data()
            object.__setattr__(self, "_runtime", runtime)
        return runtime

    @property
    def selected_attack(self) -> str:
        selected = self.runtime.get("attack")
        if selected is not None:
            return selected
        return next(iter(self.attacks))

    @property
    def selected_evolutions(self) -> dict:
        return dict(self.runtime.get("evolutions") or {})

    @property
    def selected_combo(self) -> int | None:
        combo = self.runtime.get("combo")
        if combo is None:
            return None
        return int(combo)


class RangedData(WeaponData):
    pass


class MeleeData(WeaponData):
    pass


class PrimaryData(RangedData):
    pass


class SecondaryData(RangedData):
    pass
