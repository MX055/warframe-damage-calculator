from .ranged_formatter import RangedFormatter


class PrimaryFormatter(RangedFormatter):
    def _append_unique_average_rows(self, rows: list[tuple[str, ...]], average) -> None:
        self._append(rows, "PRIMED CHAMBER MULTIPLIER", "", "", self._fmt_multiplier(average.primed_chamber_multiplier), when=float(average.primed_chamber_multiplier or 1) != 1)
