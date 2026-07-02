from __future__ import annotations

from typing import TYPE_CHECKING

from .ranged_formatter import RangedFormatter

if TYPE_CHECKING:
    from ..models import Primary


class PrimaryFormatter(RangedFormatter):
    def __init__(self, weapon: Primary) -> None:
        self.weapon: Primary = weapon