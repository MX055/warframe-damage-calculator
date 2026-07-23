from ..calculators.primary_calculator import PrimaryCalculator
from ..formatters.primary_formatter import PrimaryFormatter
from ..fields.weapon_data import PrimaryData
from ..fields.weapon_input import PrimaryStats
from .ranged import Ranged


class Primary(Ranged):
    data: PrimaryData
    stats: PrimaryCalculator
    format: PrimaryFormatter

    data_type = PrimaryData
    stats_type = PrimaryStats
    calculator_type = PrimaryCalculator
    formatter_type = PrimaryFormatter
