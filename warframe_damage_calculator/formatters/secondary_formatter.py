from __future__ import annotations

from typing import TYPE_CHECKING

from .ranged_formatter import RangedFormatter

if TYPE_CHECKING:
    from ..models import Secondary


class SecondaryFormatter(RangedFormatter):
    def __init__(self, weapon: Secondary) -> None:
        self.weapon: Secondary = weapon