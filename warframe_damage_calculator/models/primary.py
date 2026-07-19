from ..calculators.primary_calculator import PrimaryCalculator
from ..formatters.primary_formatter import PrimaryFormatter
from .fields import PrimaryData
from .ranged import Ranged


class Primary(Ranged):
    data_type = PrimaryData
    calculator_type = PrimaryCalculator
    formatter_type = PrimaryFormatter
