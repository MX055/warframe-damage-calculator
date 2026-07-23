from ..calculators.secondary_calculator import SecondaryCalculator
from ..formatters.secondary_formatter import SecondaryFormatter
from ..fields.weapon_data import SecondaryData
from ..fields.weapon_input import SecondaryStats
from .ranged import Ranged


class Secondary(Ranged):
    data: SecondaryData
    stats: SecondaryCalculator
    format: SecondaryFormatter

    data_type = SecondaryData
    stats_type = SecondaryStats
    calculator_type = SecondaryCalculator
    formatter_type = SecondaryFormatter
