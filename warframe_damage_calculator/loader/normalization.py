import re
from collections.abc import Iterable, Mapping
from typing import Any


def normalize_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def normalize_identifier(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_name(value)).strip("_")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return list(value)
    return [value]
