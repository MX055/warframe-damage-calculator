from decimal import Decimal, ROUND_HALF_UP

def true_round(number: float, decimals: int = 0) -> float:
    quant = Decimal("1").scaleb(-decimals)
    return float(Decimal(str(number)).quantize(quant, rounding=ROUND_HALF_UP))