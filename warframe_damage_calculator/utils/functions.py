from decimal import ROUND_HALF_UP, Decimal

from .types import Number


def true_round(number: Number, decimals: Number = 0):
    quant = Decimal("1").scaleb(-decimals)
    return float(Decimal(str(number)).quantize(quant, rounding=ROUND_HALF_UP))


def clamp(value: Number, minimum: Number | None = None, maximum: Number | None = None):
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value
