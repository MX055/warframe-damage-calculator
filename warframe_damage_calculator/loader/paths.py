"""Load database JSON from filesystem paths or the bundled package resource."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, TextIO


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def load_json_stream(stream: TextIO) -> dict[str, Any]:
    return json.load(stream)


def load_bundled_database() -> dict[str, Any]:
    resource = files("warframe_damage_calculator.database").joinpath("database.json")
    with resource.open("r", encoding="utf-8") as file:
        return json.load(file)
