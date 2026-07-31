from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal


type ImplementationState = Literal["implemented", "partial", "not_implemented", "unknown"]
IMPLEMENTATION_STATES = frozenset({"implemented", "partial", "not_implemented", "unknown"})


@dataclass(frozen=True, slots=True)
class ImplementationStatus:
    state: ImplementationState = "implemented"
    missing_features: tuple[str, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.state not in IMPLEMENTATION_STATES: raise ValueError(f"invalid implementation state {self.state!r}")
        features = tuple(dict.fromkeys(str(feature).strip().lower() for feature in self.missing_features if str(feature).strip()))
        if self.state == "implemented" and features: raise ValueError("implemented objects cannot declare missing features")
        if self.state in {"partial", "not_implemented"} and not features: raise ValueError(f"{self.state} objects must declare missing features")
        object.__setattr__(self, "missing_features", features)
        if self.notes is not None:
            notes = self.notes.strip()
            object.__setattr__(self, "notes", notes or None)

    @property
    def implemented(self) -> bool:
        return self.state == "implemented"

    @classmethod
    def from_record(cls, record: Mapping[str, Any] | str | None) -> ImplementationStatus:
        if record is None: return cls()
        if isinstance(record, str): return cls(state=record)
        unknown = set(record) - {"state", "missing_features", "notes"}
        if unknown: raise TypeError(f"unknown implementation status fields: {', '.join(sorted(unknown))}")
        features = record.get("missing_features", ())
        if not isinstance(features, (list, tuple)): raise TypeError("implementation_status.missing_features must be a list")
        return cls(state=str(record.get("state", "implemented")), missing_features=tuple(str(feature) for feature in features), notes=None if record.get("notes") is None else str(record["notes"]))

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {"state": self.state}
        if self.missing_features: record["missing_features"] = list(self.missing_features)
        if self.notes is not None: record["notes"] = self.notes
        return record


class ImplementationWarning(UserWarning):
    pass
