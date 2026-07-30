from __future__ import annotations

from ..domain.results import AttackResult
from ..domain.weapons import Weapon
from .calculator import calculate_weapon
from .contributions import removal_contributions, shapley_contributions


def _state_fingerprint(weapon: Weapon) -> int:
    target = weapon.target
    target_state = None if target is None else (target.name, target.faction, target.base_level, repr(target.stats), repr(target.bodyparts), repr(target.modifiers), repr(target.runtime.as_dict()))
    build_state = tuple((upgrade.name, upgrade.implemented, repr(upgrade.runtime.as_dict())) for upgrade in weapon.build)
    weapon_state = (weapon.name, weapon.type, weapon.subtype, weapon.reload_time, weapon.magazine_size, weapon.recharge_delay, weapon.recharge_rate, weapon.incarnon_charges, weapon.incarnon_recharge_count, repr(weapon.attacks), repr(weapon.evolutions), repr(weapon.traits), repr(weapon.combo), repr(weapon.runtime.as_dict()))
    return hash(repr((weapon_state, build_state, target_state)))


class WeaponResults:
    __slots__ = ("weapon", "_attacks", "_main", "_fingerprint")

    def __init__(self, weapon: Weapon, *, resolve: bool = True) -> None:
        self.weapon = weapon
        self._attacks: dict[str, AttackResult] = {}
        self._main: AttackResult | None = None
        self._fingerprint: int | None = None
        if resolve: self.resolve()

    @property
    def attacks(self) -> dict[str, AttackResult]:
        self._ensure_current()
        return self._attacks

    @property
    def main(self) -> AttackResult:
        self._ensure_current()
        if self._main is None: raise RuntimeError("weapon results are unresolved")
        return self._main

    @property
    def child(self) -> list[AttackResult]:
        return [self.attacks[name] for name in self.main.children]

    def _ensure_current(self) -> None:
        if self._main is None or self._fingerprint != _state_fingerprint(self.weapon): self.resolve()

    def resolve(self) -> None:
        self._attacks = calculate_weapon(self.weapon)
        self._main = self._attacks[self.weapon.runtime.attack]
        self._fingerprint = _state_fingerprint(self.weapon)

    def removal_contributions(self, target: str = "total_dps") -> dict[str, float]:
        return removal_contributions(self.weapon, target)

    def shapley_contributions(self, target: str = "total_dps") -> dict[str, float]:
        return shapley_contributions(self.weapon, target)
