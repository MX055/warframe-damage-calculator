from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .attacks import Inheritance, RelatedAttacks, _parse_children
from .effects import Automatic, Source
from .scaled_values import UpgradeValue, is_scaled_value_record, resolve_scalar


GENERATED_ATTACK_STAT = "generated_attack"
GENERATED_ATTACK_RECORD_FIELDS = frozenset({"name", "parent", "children", "inheritance", "automatic"})
ELEMENTAL_DAMAGE_TYPES = ("heat", "cold", "electricity", "toxin", "blast", "radiation", "gas", "magnetic", "viral", "corrosive")


def resolve_generated_payload(value: object, rank: int, max_rank: int) -> object:
    if isinstance(value, UpgradeValue): return resolve_scalar(value, rank, max_rank)
    if isinstance(value, Source):
        record: dict[str, object] = {"source": value.path}
        multiplier = value.resolve_multiplier(rank, max_rank)
        if multiplier != 1: record["multiplier"] = multiplier
        if value.default is not None: record["default"] = value.default
        return record
    if is_scaled_value_record(value): return resolve_scalar(UpgradeValue.from_record(value, default_rank_scale=False), rank, max_rank)
    if isinstance(value, Mapping):
        if "source" in value and set(value) <= {"source", "multiplier", "default"}:
            return resolve_generated_payload(Source.from_record(value), rank, max_rank)
        return {key: resolve_generated_payload(item, rank, max_rank) for key, item in value.items()}
    if isinstance(value, list): return [resolve_generated_payload(item, rank, max_rank) for item in value]
    return deepcopy(value)


@dataclass(slots=True)
class GeneratedAttack:
    name: str
    parent: RelatedAttacks
    children: list[str] = field(default_factory=list)
    inheritance: Inheritance | None = None
    automatic: Automatic | None = None

    def __post_init__(self) -> None:
        self.name = str(self.name)
        if not self.name: raise ValueError("generated attack name is required")
        if isinstance(self.parent, Mapping): self.parent = RelatedAttacks.from_record(self.parent)
        if not isinstance(self.parent, RelatedAttacks): raise TypeError("generated attack parent must be a RelatedAttacks selector")
        self.children = _parse_children(self.children)
        if isinstance(self.inheritance, Mapping): self.inheritance = Inheritance.from_record(self.inheritance)
        if isinstance(self.automatic, Mapping): self.automatic = Automatic.from_record(self.automatic)

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> GeneratedAttack:
        if "links" in record: raise ValueError("generated attack field 'links' was removed; use parent and children")
        if "override" in record: raise ValueError("generated attack field 'override' was removed; use inheritance.override")
        if set(record) - GENERATED_ATTACK_RECORD_FIELDS: raise ValueError(f"unknown generated attack fields: {sorted(set(record) - GENERATED_ATTACK_RECORD_FIELDS)}")
        if "name" not in record: raise ValueError("generated attack name is required")
        if "parent" not in record: raise ValueError("generated attack parent is required")
        return cls(
            name=str(record["name"]),
            parent=RelatedAttacks.from_record(record["parent"]),
            children=_parse_children(record.get("children")),
            inheritance=Inheritance.from_record(record.get("inheritance")),
            automatic=Automatic.from_record(record.get("automatic")),
        )

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {"name": self.name, "parent": self.parent.to_record()}
        if self.children: record["children"] = list(self.children)
        if self.inheritance is not None and self.inheritance: record["inheritance"] = self.inheritance.to_record()
        if self.automatic is not None and self.automatic.to_channel(): record["automatic"] = self.automatic.to_record()
        return record

    def to_generated_value(self) -> dict[str, Any]:
        """Serialize generated-attack payload without automatic (stored on Effect.automatic)."""
        record = self.to_record()
        record.pop("automatic", None)
        return record

    def copy(self) -> GeneratedAttack:
        return GeneratedAttack(name=self.name, parent=self.parent.copy(), children=list(self.children), inheritance=None if self.inheritance is None else self.inheritance.copy(), automatic=self.automatic)
