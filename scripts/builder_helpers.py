import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from slpp import slpp as lua

ROOT = Path(__file__).resolve().parents[1]

OUTPUT_PATHS = {
    "primaries": ROOT / "database" / "primaries.json",
    "secondaries": ROOT / "database" / "secondaries.json",
    "melees": ROOT / "database" / "melees.json",
    "mods": ROOT / "database" / "mods.json",
    "arcanes": ROOT / "database" / "arcanes.json",
}

WIKI_LUA_CACHE_PATHS = {
    "primary": ROOT / "database" / "wiki_primary.lua",
    "secondary": ROOT / "database" / "wiki_secondary.lua",
    "melee": ROOT / "database" / "wiki_melee.lua",
    "mods": ROOT / "database" / "wiki_mods.lua",
    "arcane": ROOT / "database" / "wiki_arcane.lua",
}

WIKI_MODULE_TITLES = {
    "primary": "Module:Weapons/data/primary",
    "secondary": "Module:Weapons/data/secondary",
    "melee": "Module:Weapons/data/melee",
    "mods": "Module:Mods/data",
    "arcane": "Module:Arcane/data",
}

WIKI_API = "https://warframe.fandom.com/api.php"

PRIMARY_ATTACK_NAMES = {
    "Normal Attack",
    "Rocket Impact",
    "Auto",
    "Auto Mode",
    "Full Auto Mode",
    "Fully Spooled",
    "Slug Impact",
    "Buckshot",
    "Charged Shot",
    "Projectile Impact",
    "Grenade Impact",
    "Arrow Impact",
    "Cannon Mode Projectile",
    "Beam",
}

EXPLOSION_ATTACK_NAMES = {
    "Explosion",
    "Rocket Explosion",
    "Radial Attack",
    "Glass Explosion",
    "Charged Radial Attack",
    "Projectile Explosion",
    "Grenade Explosion",
    "Grenade Detonation",
    "Bubble Collapse",
    "Arrow Explosion",
    "Cannon Mode Explosion",
    "Auto AoE",
    "Poison Cloud",
}

Stats = dict[str, Any]

def fetch_wiki_module(module_name: str) -> dict:
    if module_name not in WIKI_MODULE_TITLES:
        raise ValueError(f"Unknown wiki module: {module_name}")

    query = {
        "action": "query",
        "prop": "revisions",
        "titles": WIKI_MODULE_TITLES[module_name],
        "rvprop": "content",
        "rvslots": "main",
        "formatversion": "2",
        "format": "json",
    }
    url = f"{WIKI_API}?{urlencode(query)}"
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json,text/plain,*/*",
        },
    )

    content = None
    try:
        with urlopen(req) as resp:
            payload = json.load(resp)
        content = payload["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    except HTTPError:
        cache_path = WIKI_LUA_CACHE_PATHS.get(module_name)
        if cache_path and cache_path.exists():
            content = cache_path.read_text(encoding="utf-8")

    if not content:
        raise RuntimeError(f"Could not retrieve wiki {module_name} module source")

    content = content.replace("math.huge", "1e30")
    content = re.sub(r"(?m)--.*$", "", content)
    content = re.sub(r"^\s*return\s*", "", content, count=1)
    return lua.decode(content)


def normalize_lua_lists(obj):
    if isinstance(obj, dict):
        if obj and all(isinstance(k, int) for k in obj.keys()):
            return [normalize_lua_lists(obj[k]) for k in sorted(obj.keys())]
        return {k: normalize_lua_lists(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_lua_lists(v) for v in obj]
    return obj


def load_wiki_records(module_name: str, key: str | None = None) -> dict[str, Any]:
    module_data = normalize_lua_lists(fetch_wiki_module(module_name))
    if key is None:
        return module_data
    return module_data.get(key, {})


def normalize_damage_keys(damage_dist: dict[str, Any]) -> dict[str, Any]:
    return {damage_type.lower(): value for damage_type, value in damage_dist.items()}


def merge_stats(target: Stats, incoming: Stats) -> None:
    if "damage_dist" in incoming and isinstance(incoming["damage_dist"], dict):
        target.setdefault("damage_dist", {}).update(incoming["damage_dist"])
        incoming = {key: value for key, value in incoming.items() if key != "damage_dist"}
    for key, value in incoming.items():
        target[key] = value


def sorted_records(records: dict[str, Stats]) -> dict[str, Stats]:
    return {name: records[name] for name in sorted(records)}


def collect_records(records_by_name: dict[str, dict[str, Any]], build_record: Callable[[str, dict[str, Any]], Stats | None], skipped_header: str, skipped_line: Callable[[str, dict[str, Any]], str | None] | None = None) -> tuple[dict[str, Stats], int]:
    records: dict[str, Stats] = {}
    skipped = 0

    print(skipped_header)
    for name, source in records_by_name.items():
        record = build_record(name, source)
        if record is None:
            skipped += 1
            if skipped_line is not None:
                line = skipped_line(name, source)
                if line:
                    print(line)
            continue
        records[name] = record

    return sorted_records(records), skipped


def compact_json(obj, level: int = 0) -> str:
    indent = " " * 4 * level
    next_indent = " " * 4 * (level + 1)

    if isinstance(obj, dict):
        if not obj:
            return "{}"
        parts = []
        for key, value in obj.items():
            formatted_key = json.dumps(key, ensure_ascii=False)
            parts.append(f"{next_indent}{formatted_key}: {compact_json(value, level + 1)}")
        return "{\n" + ",\n".join(parts) + "\n" + indent + "}"

    if isinstance(obj, list):
        if not obj:
            return "[]"
        return "[" + ", ".join(compact_json(v, 0) for v in obj) + "]"

    return json.dumps(obj, ensure_ascii=False)


def write_json_file(path: Path, data: dict) -> None:
    path.write_text(compact_json(data) + "\n", encoding="utf-8")
    print(f"wrote_file={path}")



















