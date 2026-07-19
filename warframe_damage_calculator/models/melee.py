from ..calculators.melee_calculator import MeleeCalculator
from ..formatters.melee_formatter import MeleeFormatter
from .fields import MeleeData
from .weapon import Weapon


class Melee(Weapon):
    data_type = MeleeData
    calculator_type = MeleeCalculator
    formatter_type = MeleeFormatter
