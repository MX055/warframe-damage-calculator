from .ranged_formatter import RangedFormatter


class PrimaryFormatter(RangedFormatter):
    def _append_unique_average_rows(self, rows: list[tuple[str, ...]], average) -> None:
        self._append(rows, "FIRST SHOT DAMAGE MULTIPLIER", "", "", self._fmt_multiplier(average.first_shot_damage_multiplier), when=float(average.first_shot_damage_multiplier or 1) != 1)
