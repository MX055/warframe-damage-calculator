from .ranged_formatter import RangedFormatter


class SecondaryFormatter(RangedFormatter):
    def _append_unique_average_rows(self, rows: list[tuple[str, ...]], average) -> None:
        self._append(rows, "SECONDARY ENERVATE BONUS", "", "", self._with_weakpoint(self._fmt_bonus_percent(average.secondary_enervate_bonus), self._fmt_bonus_percent(average.weakpoint_secondary_enervate_bonus)), when=float(average.secondary_enervate_bonus or 0) > 0)
