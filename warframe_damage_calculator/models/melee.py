from ..calculators.melee_calculator import MeleeCalculator
from ..formatters.melee_formatter import MeleeFormatter
from .fields import MeleeData, MeleeStats
from .weapon import Weapon


class Melee(Weapon):
    data: MeleeData
    stats: MeleeCalculator
    format: MeleeFormatter

    data_type = MeleeData
    mode_stats_type = MeleeStats
    calculator_type = MeleeCalculator
    formatter_type = MeleeFormatter
