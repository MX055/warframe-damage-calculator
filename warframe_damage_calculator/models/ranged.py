from ..calculators.ranged_calculator import RangedCalculator
from ..formatters.ranged_formatter import RangedFormatter
from .fields import RangedData, RangedStats
from .weapon import Weapon


class Ranged(Weapon):
    data: RangedData
    stats: RangedCalculator
    format: RangedFormatter

    data_type = RangedData
    mode_stats_type = RangedStats
    calculator_type = RangedCalculator
    formatter_type = RangedFormatter
