from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from .effects import Source
from .scaled_values import UpgradeValue, is_scaled_value_record, resolve_scalar


GENERATED_ATTACK_STAT = "generated_attack"
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
