from ..core.data import Data
from ..utils.types import Number
from .evolution_data import Evolutions
from .weapon_input import AttackStats
from .typed_mapping import NamedTypedMapping


class Attack(Data):
    name: str = ""
    trigger: str | None = None
    delivery: str | None = None
    form: str = "normal"
    category: str = "normal"
    aoe: bool = False
    children: list[str] = []
    stats: AttackStats = AttackStats()


class Attacks(NamedTypedMapping):
    _item_type = Attack


class WeaponAmmo(Data):
    pass


class WeaponCombo(Data):
    max_combo: int = 12
    combo_interval: int = 20


class WeaponRuntime(Data):
    pass


class WeaponData(Data):
    name: str = ""
    type: str | None = None
    subtype: str | None = None
    disposition: Number = 0.0
    exalted: bool = False
    pseudo_exalted: bool = False
    progenitor: bool = False
    companion: bool = False
    ammo: WeaponAmmo = WeaponAmmo()
    attacks: Attacks = Attacks()
    evolutions: Evolutions = Evolutions()
    runtime: WeaponRuntime = WeaponRuntime()

    @property
    def selected_attack(self) -> str:
        return str(self.runtime.attack)

    @property
    def selected_evolutions(self) -> dict:
        return dict(self.runtime.evolutions)

    @property
    def selected_combo(self) -> int:
        return int(self.runtime.combo)

    @property
    def selected_stance_combo(self) -> str:
        return str(self.runtime.stance_combo)

    @property
    def selected_ability_strength(self) -> float:
        """Warframe Ability Strength as a multiplier (1.0 = 100%)."""
        return float(self.runtime.ability_strength)


class RangedData(WeaponData):
    pass


class MeleeData(WeaponData):
    combo: WeaponCombo = WeaponCombo()


class PrimaryData(RangedData):
    pass


class SecondaryData(RangedData):
    pass
