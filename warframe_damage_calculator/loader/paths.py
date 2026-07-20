import json
import sys
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
SOURCE_DATABASE_PATH = DATA_DIR.parents[1] / "database" / "database.json"
INSTALLED_DATABASE_PATH = Path(sys.prefix) / "database" / "database.json"
DEFAULT_DATABASE_PATH = (
    SOURCE_DATABASE_PATH
    if SOURCE_DATABASE_PATH.exists()
    else INSTALLED_DATABASE_PATH
)


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)
