from __future__ import annotations

from dataclasses import fields
from typing import Self


class Addable:
    def __add__(self, other: Self) -> Self:
        if not isinstance(other, type(self)):
            return NotImplemented
        
        combined: dict[str, object] = {}
        for field in fields(self):
            left = getattr(self, field.name)
            right = getattr(other, field.name)

            if isinstance(left, bool) and isinstance(right, bool):
                combined[field.name] = left or right
                continue

            try: combined[field.name] = left + right
            except TypeError: return NotImplemented
            
        return type(self)(**combined)

    def __radd__(self, other: int | float) -> Self:
        if other == 0:
            return self
        return NotImplemented