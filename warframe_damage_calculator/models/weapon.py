from __future__ import annotations

from typing import Any, Self, TypeVar, Unpack

from ..calculators import WeaponCalculator
from ..fields import WeaponFields
from ..formatters import WeaponFormatter
from ..states import WeaponState
from .upgrade import Upgrade
from .build import Build
from .dist import dist


TState = TypeVar("TState", bound=WeaponState)


class Weapon:
    def __init__(self, **weapon_fields: Unpack[WeaponFields]):
        base_state = self._create_state(WeaponState, weapon_fields)
        self.stats = WeaponCalculator(base_state)
        self.format = WeaponFormatter(self.stats)

    @staticmethod
    def _create_state(state_class: type[TState], weapon_fields: dict[str, Any]) -> TState:
        state_fields = dict(weapon_fields)
        for field_name in ("damage", "forced_procs", "explosion_damage", "explosion_forced_procs"):
            if field_name in state_fields:
                state_fields[field_name] = dist(state_fields[field_name])
        return state_class(**state_fields)

    def configure(self, *upgrades: Build | Upgrade) -> Self:
        if all(type(upgrade) is Upgrade for upgrade in upgrades):
            build = Build(*upgrades)
        elif len(upgrades) == 1 and isinstance(upgrades[0], Build):
            build = upgrades[0]
        else:
            raise TypeError
        self.stats._set_build(build)
        return self
