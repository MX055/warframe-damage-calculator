import json
import re
from functools import partial
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
RankValues = list[float]
PatternMap = tuple[tuple[re.Pattern[str], str], ...]


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


def collect_records(records_by_name: dict[str, dict[str, Any]], build_record: Callable[[str, dict[str, Any]], Stats | None]) -> tuple[dict[str, Stats], int]:
    records: dict[str, Stats] = {}
    skipped = 0

    for name, source in records_by_name.items():
        record = build_record(name, source)
        if record is None:
            skipped += 1
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


def rank_series(max_value: float, max_rank: int, *, round_digits: int = 3) -> RankValues:
    levels = max_rank + 1
    step = max_value / levels
    return [round(step * (i + 1), round_digits) for i in range(levels)]


def has_effective_stats(record: Stats) -> bool:
    metadata_keys = {"max_rank", "compatibility_tag"}
    return any(key not in metadata_keys for key in record)


def clean_empty_damage_dist(records: dict[str, Stats]) -> dict[str, Stats]:
    for record in records.values():
        if not record.get("damage_dist"):
            record.pop("damage_dist", None)
    return records


def parse_line_numbers(line: str, percent_re: re.Pattern[str], multiplier_re: re.Pattern[str]) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    for match in percent_re.finditer(line):
        values.append((match.start(), float(match.group(1)) / 100.0))
    for match in multiplier_re.finditer(line):
        values.append((match.start(), float(match.group(1)) - 1.0))
    return values


def extract_mapped_fields(source: dict[str, Any], mapping: PatternMap) -> Stats:
    extracted: Stats = {}
    for pattern, key in mapping:
        for field_name, value in source.items():
            if not isinstance(field_name, str):
                continue
            if pattern.search(field_name):
                extracted[key] = value
                break
    return extracted


def extract_mapped_text(text: str, mapping: PatternMap) -> Stats:
    for pattern, key in mapping:
        if pattern.search(text):
            return {key: True}
    return {}


RANGED_STAT_MAP: PatternMap = (
    (re.compile(r"^CritChance$"), "crit_chance"),
    (re.compile(r"^CritMultiplier$"), "crit_damage"),
    (re.compile(r"^Damage$"), "damage_dist"),
    (re.compile(r"^FireRate$"), "fire_rate"),
    (re.compile(r"^StatusChance$"), "status_chance"),
    (re.compile(r"^Multishot$"), "multishot"),
    (re.compile(r"^Reload$"), "reload_speed"),
    (re.compile(r"^Magazine$"), "magazine_capacity"),
)

WeaponRecordBuilder = Callable[[str, dict[str, Any]], Stats | None]
UpgradeLineParser = Callable[[str, int, str], Stats]
UpgradeFilter = Callable[[dict[str, Any]], bool]
UpgradeCompatibility = Callable[[dict[str, Any]], str]
UpgradeBonusApplier = Callable[[str, dict[str, Any], int, Stats], None]
UpgradeLineSplitter = Callable[[str], list[str]]
RecordFormatter = Callable[[str, dict[str, Any]], str | None]
RecordCleanup = Callable[[dict[str, Stats]], dict[str, Stats]]


def detect_trigger_type(record: dict[str, Any]) -> str | None:
    trigger_text = str(record.get("Trigger", "")).strip().lower()
    if not trigger_text:
        return None

    auto_text = trigger_text.replace("semi-auto", "")
    if "auto" in auto_text or "held" in auto_text:
        return "auto"
    if "burst" in trigger_text.replace("mag burst", ""):
        return "burst"
    if "semi" in trigger_text:
        return "semi"
    if "active" in trigger_text:
        return "active"
    if "duplex" in trigger_text:
        return "duplex"
    if "charge" in trigger_text:
        return "charge"

    return None


def extract_ranged_attack_stats(attack: dict[str, Any]) -> Stats:
    attack_name = attack.get("AttackName")
    if attack_name in PRIMARY_ATTACK_NAMES:
        stats = extract_mapped_fields(attack, RANGED_STAT_MAP)
        if "damage_dist" in stats and isinstance(stats["damage_dist"], dict):
            stats["damage_dist"] = normalize_damage_keys(stats["damage_dist"])
        return stats

    if attack_name in EXPLOSION_ATTACK_NAMES:
        explosion_damage_dist = attack["Damage"]
        if isinstance(explosion_damage_dist, dict):
            explosion_damage_dist = normalize_damage_keys(explosion_damage_dist)
        return {"explosion_damage_dist": explosion_damage_dist}

    return {}


def build_weapon_records(
    module_name: str,
    build_record: WeaponRecordBuilder,
    generated_label: str,
    skipped_label: str,
) -> dict[str, dict]:
    return build_record_pipeline(
        module_name=module_name,
        key=None,
        build_record=build_record,
        generated_label=generated_label,
        skipped_label=skipped_label,
    )


MELEE_STAT_MAP: PatternMap = (
    (re.compile(r"^CritChance$"), "crit_chance"),
    (re.compile(r"^CritMultiplier$"), "crit_damage"),
    (re.compile(r"^Damage$"), "damage_dist"),
    (re.compile(r"^FireRate$"), "attack_speed"),
    (re.compile(r"^StatusChance$"), "status_chance"),
)


def extract_melee_attack_stats(attack: dict[str, Any]) -> Stats:
    if attack.get("AttackName") != "Normal Attack":
        return {}

    stats = extract_mapped_fields(attack, MELEE_STAT_MAP)
    if "damage_dist" in stats and isinstance(stats["damage_dist"], dict):
        stats["damage_dist"] = normalize_damage_keys(stats["damage_dist"])

    return stats


def build_melee_record(name: str, melee: dict[str, Any]) -> Stats | None:
    del name
    record: Stats = {}
    for attack in melee.get("Attacks", []):
        merge_stats(record, extract_melee_attack_stats(attack))

    if not record:
        return None

    class_name = str(melee.get("Class", "Melee")).strip() or "Melee"
    class_tags: list[str] = ["melee"]
    lower_class_name = class_name.lower()
    if lower_class_name != "melee":
        class_tags.append(lower_class_name)
    record["class_tags"] = class_tags
    return record


PRIMARY_BEAM_EXCEPTIONS = ("Panthera", "Panthera Prime", "Tenet Flux Rifle")


def build_ranged_weapon_record(
    name: str,
    weapon: dict[str, Any],
    *,
    base_type: str,
    output_type_key: str | None,
    beam_exceptions: tuple[str, ...],
) -> Stats | None:
    record: Stats = {}
    for attack in weapon.get("Attacks", []):
        merge_stats(record, extract_ranged_attack_stats(attack))

    for source_key, target_key in (("Reload", "reload_speed"), ("Magazine", "magazine_capacity")):
        if target_key not in record and source_key in weapon:
            record[target_key] = weapon[source_key]

    tags = weapon.get("CompatibilityTags", [])
    record["is_beam"] = "BEAM" in tags if name not in beam_exceptions else False

    weapon_class = str(weapon.get("Class", "primary")).strip().lower() or "primary"
    weapon_types = [base_type, weapon_class]
    if trigger_type := detect_trigger_type(weapon):
        weapon_types.append(f"{trigger_type}-{weapon_class}")
    if output_type_key is not None:
        record[output_type_key] = weapon_types
    record["class_tags"] = weapon_types.copy()

    return record or None


def build_primary_record(name: str, primary: dict[str, Any]) -> Stats | None:
    return build_ranged_weapon_record(
        name,
        primary,
        base_type="primary",
        output_type_key="type",
        beam_exceptions=PRIMARY_BEAM_EXCEPTIONS,
    )


SECONDARY_BEAM_EXCEPTIONS = ("Tenet Spirex",)


def build_secondary_record(name: str, secondary: dict[str, Any]) -> Stats | None:
    return build_ranged_weapon_record(
        name,
        secondary,
        base_type="secondary",
        output_type_key=None,
        beam_exceptions=SECONDARY_BEAM_EXCEPTIONS,
    )


SUPPORTED_ARCANE_TYPES = {"primary", "secondary", "melee"}
SUPPORTED_MOD_TYPES = {"Primary", "Pistol", "Shotgun", "Rifle", "Sniper", "Melee"}

MOD_COMPATIBILITY_MAP = {
    "Primary": "primary",
    "Pistol": "secondary",
    "Shotgun": "shotgun",
    "Rifle": "rifle",
    "Sniper": "sniper rifle",
    "Melee": "melee",
    "Semi-Rifle": "semi-rifle",
    "Semi-Shotgun": "semi-shotgun",
    "Semi-Pistol": "semi-pistol",
}

MOD_STAT_MAP: PatternMap = (
    (re.compile(r"melee damage"), "base_damage"),
    (re.compile(r"damage per status type"), "base_damage"),
    (re.compile(r"damage while invisible"), "conditional_base_damage"),
    (re.compile(r"damage to corpus"), "damage_to_corpus"),
    (re.compile(r"damage to orokin"), "damage_to_orokin"),
    (re.compile(r"damage to grineer"), "damage_to_grinier"),
    (re.compile(r"damage to infested"), "damage_to_infested"),
    (re.compile(r"damage to murmur"), "damage_to_murmur"),
    (re.compile(r"critical chance"), "crit_chance"),
    (re.compile(r"critical damage"), "crit_damage"),
    (re.compile(r"status chance"), "status_chance"),
    (re.compile(r"status damage"), "status_damage"),
    (re.compile(r"attack speed"), "attack_speed"),
    (re.compile(r"fire rate"), "fire_rate"),
    (re.compile(r"reload speed"), "reload_speed"),
    (re.compile(r"magazine capacity"), "magazine_capacity"),
    (re.compile(r"multishot"), "multishot"),
    (re.compile(r"weak point damage"), "weakpoint_damage"),
    (re.compile(r"headshot damage"), "weakpoint_damage"),
    (re.compile(r"weakpoint critical chance"), "weakpoint_crit_chance"),
    (re.compile(r"damage on first shot in magazine"), "primed_chamber"),
    (re.compile(r"chance to apply <dt_slash_color> on critical"), "hunter_munitions"),
    (re.compile(r"chance to apply a <dt_slash_color> slash status effect"), "internal_bleeding"),
    (re.compile(r"^damage$"), "base_damage"),
)
MOD_LOCK_MAP: PatternMap = (
    (re.compile(r"multishot cannot be modified"), "multishot_lock"),
    (re.compile(r"fire rate cannot be modified"), "fire_rate_lock"),
)

MOD_DAMAGE_TYPES = (
    "impact",
    "puncture",
    "slash",
    "blast",
    "corrosive",
    "gas",
    "magnetic",
    "radiation",
    "viral",
    "cold",
    "electricity",
    "heat",
    "toxin",
)
MOD_INTERNAL_DAMAGE_TYPES = {"cold": "freeze", "heat": "fire", "toxin": "poison"}
MOD_DAMAGE_TAG_TO_TYPE = {f"<dt_{MOD_INTERNAL_DAMAGE_TYPES.get(damage_type, damage_type)}_color>{damage_type}": damage_type for damage_type in MOD_DAMAGE_TYPES}

MOD_STAT_LINE_RE = re.compile(r".*?([+-]?\d+(?:\.\d+)?)%?\s*(.+)")
MOD_PERCENT_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
MOD_MULTIPLIER_RE = re.compile(r"\bx\s*([+-]?\d+(?:\.\d+)?)\b", re.I)
MOD_STACKS_RE = re.compile(r"Stacks?\s+up\s+to\s+(\d+)x\b", re.I)
MOD_STACKS_WITH_RE = re.compile(r"stacks?\s+with\b", re.I)
MOD_PER_RE = re.compile(r"\bper\b", re.I)
MOD_DURATION_RE = re.compile(r"for\s+\d+(?:\.\d+)?s\b", re.I)
MOD_IS_MULT_RE = re.compile(r"\bx\d+(?:\.\d+)?\b", re.I)

ARCANE_STACKS_RE = re.compile(r"Stacks?\s+up\s+to\s+(\d+)x\b", re.I)
ARCANE_PERCENT_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
ARCANE_MULTIPLIER_RE = re.compile(r"\bx\s*([+-]?\d+(?:\.\d+)?)\b", re.I)
ARCANE_PERCENT_DAMAGE_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%\s+damage\b", re.I)
ARCANE_STAT_PATTERNS = [
    (re.compile(r"weak\s*point\s*damage|headshot\s*multiplier|headshot\s*damage", re.I), "weakpoint_damage"),
    (re.compile(r"critical chance", re.I), "crit_chance"),
    (re.compile(r"critical damage", re.I), "crit_damage"),
    (re.compile(r"status chance", re.I), "status_chance"),
    (re.compile(r"reload speed", re.I), "reload_speed"),
    (re.compile(r"multishot", re.I), "multishot"),
    (re.compile(r"fire rate", re.I), "fire_rate"),
]


def split_mod_description_lines(description: str) -> list[str]:
    return re.split(r"(?<!:)\r\n", description.replace(r"\r\n", "\r\n"))


def split_arcane_description_lines(description: str) -> list[str]:
    text = str(description or "")
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return lines if lines else re.split(r"(?<!:)\r\n", str(description).replace(r"\r\n", "\r\n"))


def nearest_value(stat_index: int, values: list[tuple[int, float]]) -> float | None:
    if not values:
        return None
    return min(values, key=lambda item: abs(item[0] - stat_index))[1]


def build_upgrade_record(
    name: str,
    record: dict[str, Any],
    *,
    is_supported: UpgradeFilter,
    should_skip: UpgradeFilter,
    parse_line_stats: UpgradeLineParser,
    split_description_lines: UpgradeLineSplitter,
    get_compatible_weapons: UpgradeCompatibility,
    apply_bonus: UpgradeBonusApplier | None = None,
) -> Stats | None:
    if not is_supported(record) or should_skip(record):
        return None

    description = str(record.get("Description", ""))
    max_rank = int(record.get("MaxRank", 0))

    output: Stats = {}
    for line in split_description_lines(description):
        merge_stats(output, parse_line_stats(line, max_rank, name))

    if apply_bonus is not None:
        apply_bonus(name, record, max_rank, output)

    if not has_effective_stats(output):
        return None

    compatibility_tag = get_compatible_weapons(record)
    output["max_rank"] = max_rank
    output["compatibility_tag"] = compatibility_tag
    return output


def build_record_pipeline(
    *,
    module_name: str,
    key: str | None,
    build_record: Callable[[str, dict[str, Any]], Stats | None],
    generated_label: str,
    skipped_label: str | None,
    cleanup: Callable[[dict[str, Stats]], dict[str, Stats]] | None = None,
) -> dict[str, dict]:
    source_records = load_wiki_records(module_name, key)
    records, skipped = collect_records(source_records, build_record)

    if cleanup is not None:
        records = cleanup(records)

    print(f"{generated_label}={len(records)}")
    if skipped_label is not None:
        print(f"{skipped_label}={skipped}")
    return records


def build_upgrade_records(
    *,
    module_name: str,
    key: str,
    build_record: WeaponRecordBuilder,
    is_supported: UpgradeFilter,
    generated_label: str,
    skipped_label: str,
) -> dict[str, dict]:
    return build_record_pipeline(
        module_name=module_name,
        key=key,
        build_record=build_record,
        generated_label=generated_label,
        skipped_label=skipped_label,
        cleanup=clean_empty_damage_dist,
    )


def is_supported_mod(record: dict[str, Any]) -> bool:
    return record.get("Type", "") in SUPPORTED_MOD_TYPES


def should_skip_mod(record: dict[str, Any]) -> bool:
    return "tennokai" in str(record.get("Description", "")).lower()


def get_mod_set_name(record: dict[str, Any]) -> str | None:
    set_label = str(record.get("Set", "")).strip()
    if not set_label:
        return None
    return re.sub(r"\s+set$", "", set_label, flags=re.IGNORECASE)


def get_mod_compatible_weapons(record: dict[str, Any]) -> str:
    mod_type = str(record.get("Type", "")).strip()
    if "Only compatible with Semi-Auto Trigger" in str(record.get("Description", "")):
        return MOD_COMPATIBILITY_MAP.get(f"Semi-{mod_type}", "")
    return MOD_COMPATIBILITY_MAP.get(mod_type, "")


def apply_mod_set_bonus(name: str, set_name: str | None, max_rank: int, stats: Stats) -> None:
    if set_name == "Vigilante":
        stats["vigilante_bonus"] = 0.05

    if set_name != "Sacrificial":
        return

    if name == "Sacrificial Pressure":
        stats["conditional_base_damage"] = rank_series(0.275, max_rank)
    else:
        stats["conditional_crit_chance"] = rank_series(0.55, max_rank)


def parse_mod_stat_line(line: str, max_rank: int) -> tuple[list[float] | None, str | None]:
    match = MOD_STAT_LINE_RE.search(line)
    if not match:
        return None, None

    values = parse_line_numbers(line, MOD_PERCENT_RE, MOD_MULTIPLIER_RE)
    value = values[0][1] if values else None

    if value is None:
        max_bonus = float(match.group(1))
        value = max_bonus - 1 if MOD_IS_MULT_RE.search(line.replace("(x2", "")) else max_bonus / 100

    return rank_series(value, max_rank), match.group(2).lower()


def extract_mod_primary_stat(text: str, bonus: list[float]) -> Stats:
    for pattern, key in MOD_STAT_MAP:
        if pattern.search(text):
            return {key: bonus}
    return {}


def extract_mod_damage_distribution(text: str, bonus: list[float]) -> Stats:
    damage_type = MOD_DAMAGE_TAG_TO_TYPE.get(text)
    if damage_type is None:
        return {}
    return {damage_type: bonus}


def extract_mod_locks(text: str) -> dict[str, bool]:
    return extract_mapped_text(text, MOD_LOCK_MAP)


def apply_mod_conditions(stat: Stats, line: str) -> Stats:
    lowered = line.lower()

    if stacks := MOD_STACKS_RE.search(line):
        stat = {f"stacking_{key}": value for key, value in stat.items()}
        stat["max_stacks"] = int(stacks.group(1))
    elif MOD_STACKS_WITH_RE.search(line):
        if stat:
            stat = {f"stacking_{key}": value for key, value in stat.items()}
            stat["max_stacks"] = None
    elif MOD_PER_RE.search(line) and "per rank" not in lowered:
        if stat:
            stat = {f"stacking_{key}": value for key, value in stat.items()}
            stat["max_stacks"] = None
    elif MOD_DURATION_RE.search(line):
        stat = {f"conditional_{key}": value for key, value in stat.items()}

    if "(x2 for" in lowered and stat:
        first_key = next(iter(stat), None)
        if first_key is not None:
            stat[f"conditional_{first_key}"] = stat[first_key]

    return stat


def parse_mod_line_stats(line: str, max_rank: int, record_name: str | None = None) -> Stats:
    if lock_stat := extract_mod_locks(line.lower()):
        return lock_stat

    bonus_values, stat_text = parse_mod_stat_line(line, max_rank)
    if bonus_values is None or stat_text is None:
        return {}

    parsed_stat: Stats = {}
    if damage_dist := extract_mod_damage_distribution(stat_text, bonus_values):
        parsed_stat["damage_dist"] = damage_dist

    parsed_stat.update(extract_mod_primary_stat(stat_text, bonus_values))
    parsed_stat.update(extract_mod_locks(stat_text))

    if record_name in {"Galvanized Aptitude", "Galvanized Savvy", "Galvanized Shot"}:
        for key in tuple(parsed_stat):
            if key.endswith("base_damage"):
                parsed_stat.pop(key, None)

    return apply_mod_conditions(parsed_stat, line)


def build_mod_record(name: str, record: dict[str, Any]) -> Stats | None:
    def _apply_bonus(mod_name: str, mod_record: dict[str, Any], max_rank: int, stats: Stats) -> None:
        apply_mod_set_bonus(mod_name, get_mod_set_name(mod_record), max_rank, stats)

    def _parse(line: str, max_rank: int, record_name: str) -> Stats:
        return parse_mod_line_stats(line, max_rank, record_name)

    return build_upgrade_record(
        name,
        record,
        is_supported=is_supported_mod,
        should_skip=should_skip_mod,
        parse_line_stats=_parse,
        split_description_lines=split_mod_description_lines,
        get_compatible_weapons=get_mod_compatible_weapons,
        apply_bonus=_apply_bonus,
    )


def is_supported_arcane(record: dict[str, Any]) -> bool:
    arcane_type = str(record.get("Type", "")).strip().lower()
    return arcane_type in SUPPORTED_ARCANE_TYPES


def get_arcane_compatible_weapons(record: dict[str, Any]) -> str:
    arcane_type = str(record.get("Type", "")).strip().lower()
    return arcane_type if arcane_type in SUPPORTED_ARCANE_TYPES else ""


def parse_arcane_line_stats(line: str, max_rank: int, record_name: str) -> Stats:
    stats: Stats = {}
    values = parse_line_numbers(line, ARCANE_PERCENT_RE, ARCANE_MULTIPLIER_RE)

    if record_name == "Secondary Enervate":
        stats["secondary_enervate"] = [rank + 1 for rank in range(max_rank + 1)]
        return stats
    if record_name == "Melee Duplicate":
        stats["melee_duplicate"] = [0.25 + rank * 0.15 for rank in range(max_rank + 1)]
        return stats
    if record_name == "Melee Doughty":
        stats["staking_crit_damage"] = [0.5 + rank * 0.1 for rank in range(max_rank + 1)]
        stats["max_stacks"] = None
        return stats
    if record_name == "Melee Animosity":
        return stats

    for pattern, stat_key in ARCANE_STAT_PATTERNS:
        for match in pattern.finditer(line):
            value = nearest_value(match.start(), values)
            if value is None:
                continue
            if record_name == "Secondary Outburst" and stat_key == "crit_chance":
                continue
            stats[stat_key] = rank_series(value, max_rank)

    if percent_damage := ARCANE_PERCENT_DAMAGE_RE.search(line):
        stats["base_damage"] = rank_series(float(percent_damage.group(1)) / 100.0, max_rank)

    if stacks := ARCANE_STACKS_RE.search(line):
        stack_count = int(stacks.group(1))
        stacked: Stats = {f"stack_{key}": value for key, value in stats.items()}
        stacked["max_stacks"] = stack_count
        return stacked

    return stats


def build_arcane_record(name: str, record: dict[str, Any]) -> Stats | None:
    return build_upgrade_record(
        name,
        record,
        is_supported=is_supported_arcane,
        should_skip=lambda _: False,
        parse_line_stats=parse_arcane_line_stats,
        split_description_lines=split_arcane_description_lines,
        get_compatible_weapons=get_arcane_compatible_weapons,
    )


BUILD_PIPELINES = (
    ("melees", partial(build_weapon_records, "melee", build_melee_record, "generated_melees", "skipped melees:")),
    ("primaries", partial(build_weapon_records, "primary", build_primary_record, "generated_primaries", "skipped primaries:")),
    ("secondaries", partial(build_weapon_records, "secondary", build_secondary_record, "generated_secondaries", "skipped secondaries:")),
    (
        "mods",
        partial(
            build_upgrade_records,
            module_name="mods",
            key="Mods",
            build_record=build_mod_record,
            is_supported=is_supported_mod,
            generated_label="generated_mods",
            skipped_label="skipped_mods",
        ),
    ),
    (
        "arcanes",
        partial(
            build_upgrade_records,
            module_name="arcane",
            key="Arcanes",
            build_record=build_arcane_record,
            is_supported=is_supported_arcane,
            generated_label="generated_arcanes",
            skipped_label="skipped_arcanes",
        ),
    ),
)


def build_all() -> None:
    for output_key, build_dataset in BUILD_PIPELINES:
        write_json_file(OUTPUT_PATHS[output_key], build_dataset())


def main() -> None:
    build_all()


if __name__ == "__main__":
    main()
