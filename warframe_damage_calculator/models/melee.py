from ..calculators.melee_calculator import MeleeCalculator
from ..formatters.melee_formatter import MeleeFormatter
from ..fields.weapon_data import MeleeData
from ..fields.weapon_input import MeleeStats
from .weapon import Weapon


class Melee(Weapon):
    data: MeleeData
    stats: MeleeCalculator
    format: MeleeFormatter

    data_type = MeleeData
    stats_type = MeleeStats
    calculator_type = MeleeCalculator
    formatter_type = MeleeFormatter
