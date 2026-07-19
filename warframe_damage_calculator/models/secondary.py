from ..calculators.secondary_calculator import SecondaryCalculator
from ..formatters.secondary_formatter import SecondaryFormatter
from .fields import SecondaryData
from .ranged import Ranged


class Secondary(Ranged):
    data_type = SecondaryData
    calculator_type = SecondaryCalculator
    formatter_type = SecondaryFormatter
