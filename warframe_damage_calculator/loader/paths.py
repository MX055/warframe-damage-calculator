import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = DATA_DIR.parents[1] / "database" / "database.json"


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)
