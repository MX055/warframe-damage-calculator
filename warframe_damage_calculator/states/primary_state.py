from dataclasses import dataclass

from .ranged_state import RangedState


@dataclass
class PrimaryState(RangedState):
    hunter_munitions: float = 0.0
    primed_chamber: float = 0.0
    vigilante_bonus: float = 0.0