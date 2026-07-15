from decimal import ROUND_HALF_UP, Decimal


def true_round(number: float, decimals: int = 0) -> float:
    quant = Decimal("1").scaleb(-decimals)
    return float(Decimal(str(number)).quantize(quant, rounding=ROUND_HALF_UP))


def clamp(value: float, minimum: float | None = None, maximum: float | None = None) -> float:
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value
