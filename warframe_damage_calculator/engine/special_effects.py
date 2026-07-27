"""Deferred special-effect payload helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any


def serialize_deferred(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in payload.items()}


def iter_deferred(*sources: Sequence[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    entries: list[Mapping[str, Any]] = []
    for source in sources:
        if source: entries.extend(source)
    return entries
