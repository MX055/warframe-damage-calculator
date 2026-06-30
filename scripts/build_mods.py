import re
from typing import Any

from builder_helpers import OUTPUT_PATHS, collect_records, load_wiki_records, merge_stats, write_json_file

DAMAGE_TYPES = (
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
INTERNAL_DAMAGE_TYPES = {"cold": "freeze", "heat": "fire", "toxin": "poison"}
SUPPORTED_MOD_TYPES = {"Primary", "Pistol", "Shotgun", "Rifle", "Sniper", "Melee"}
MOD_COMPATIBILITY_MAP = {
    "Primary": "primary",
    "Pistol": "secondary",
    "Shotgun": "shotgun",
    "Rifle": "primary",
    "Sniper": "sniper",
    "Melee": "melee",
    "Semi-Rifle": "semi-rifle",
    "Semi-Shotgun": "semi-shotgun",
    "Semi-Pistol": "semi-pistol"
}

STAT_MAP = {
    "damage": "base_damage",
    "melee damage": "base_damage",
    "damage while invisible": "conditional_base_damage",
    "damage to corpus": "damage_to_corpus",
    "damage to orokin": "damage_to_orokin",
    "damage to grineer": "damage_to_grinier",
    "damage to infested": "damage_to_infested",
    "damage to murmur": "damage_to_murmur",
    "critical chance": "crit_chance",
    "critical damage": "crit_damage",
    "status chance": "status_chance",
    "status damage": "status_damage",
    "attack speed": "attack_speed",
    "fire rate": "fire_rate",
    "reload speed": "reload_speed",
    "magazine capacity": "magazine_capacity",
    "multishot": "multishot",
    "weak point damage": "weakpoint_damage",
    "headshot damage": "weakpoint_damage",
    "weakpoint critical chance": "weakpoint_crit_chance",
    "damage on first shot in magazine": "primed_chamber",
    "chance to apply <dt_slash_color> on critical": "hunter_munitions",
    "chance to apply a <dt_slash_color> slash status effect": "internal_bleeding",
}
LOCK_MAP = {
    "multishot cannot be modified": "multishot_lock",
    "fire rate cannot be modified": "fire_rate_lock",
}

STAT_LINE_RE = re.compile(r".*?([+-]?\d+(?:\.\d+)?)%?\s*(.+)")
STACKS_RE = re.compile(r"Stacks?\s+up\s+to\s+(\d+)x\b", re.I)
DURATION_RE = re.compile(r"for\s+\d+(?:\.\d+)?s\b", re.I)
IS_MULT_RE = re.compile(r"\bx\d+(?:\.\d+)?\b", re.I)
BASE_DAMAGE_PATTERN = "damage"

DAMAGE_TAG_TO_TYPE = {
    f"<dt_{INTERNAL_DAMAGE_TYPES.get(damage_type, damage_type)}_color>{damage_type}": damage_type
    for damage_type in DAMAGE_TYPES
}

Stats = dict[str, Any]
RankValues = list[float]
ParsedStatLine = tuple[RankValues, str] | tuple[None, None]


def rank_series(max_value: float, max_rank: int, *, round_digits: int = 3) -> RankValues:
    levels = max_rank + 1
    step = max_value / levels
    return [round(step * (i + 1), round_digits) for i in range(levels)]


def prefix_stat_keys(stat: Stats, prefix: str) -> Stats:
    return {f"{prefix}{key}": value for key, value in stat.items()}


def split_stat_descriptions(description: str) -> list[str]:
    return re.split(r"(?<!:)\r\n", description.replace(r"\r\n", "\r\n"))


def parse_stat_line(line: str, max_rank: int) -> ParsedStatLine:
    match = STAT_LINE_RE.search(line)
    if not match:
        return None, None
    max_bonus = float(match.group(1))
    bonus_values = rank_series(max_bonus if IS_MULT_RE.search(line.replace("(x2", "")) else max_bonus / 100, max_rank)
    stat_text = match.group(2).lower()
    return bonus_values, stat_text


def extract_damage_distribution(text: str, bonus: RankValues) -> Stats:
    damage_type = DAMAGE_TAG_TO_TYPE.get(text)
    if damage_type is None:
        return {}
    return {damage_type: bonus}


def extract_primary_stat(text: str, bonus: RankValues) -> Stats:
    if text == BASE_DAMAGE_PATTERN:
        return {STAT_MAP[BASE_DAMAGE_PATTERN]: bonus}

    for pattern, key in STAT_MAP.items():
        if pattern == BASE_DAMAGE_PATTERN:
            continue
        if pattern in text:
            return {key: bonus}

    return {}


def extract_locks(text: str) -> dict[str, bool]:
    for pattern, key in LOCK_MAP.items():
        if pattern in text:
            return {key: True}
    return {}


def apply_conditions(stat: Stats, stat_description: str) -> Stats:
    lowered = stat_description.lower()

    if stacks := STACKS_RE.search(stat_description):
        stat = prefix_stat_keys(stat, "stacking_")
        stat["max_stacks"] = int(stacks.group(1))
    elif "melee damage per status type" in lowered:
        stat = prefix_stat_keys(stat, "stacking_")
        stat["max_stacks"] = None
    elif DURATION_RE.search(stat_description):
        stat = prefix_stat_keys(stat, "conditional_")

    if "(x2 for" in lowered and stat:
        first_key = next(iter(stat), None)
        if first_key is not None:
            stat[f"conditional_{first_key}"] = stat[first_key]

    return stat


def apply_set_bonus(name: str, set_name: str | None, max_rank: int, stats: Stats) -> None:
    if set_name == "Vigilante":
        stats["vigilante_bonus"] = 0.05

    if set_name != "Sacrificial":
        return

    if name == "Sacrificial Pressure":
        stats["conditional_base_damage"] = rank_series(0.275, max_rank)
    else:
        stats["conditional_crit_chance"] = rank_series(0.55, max_rank)


def is_supported_mod(mod: dict[str, Any]) -> bool:
    return mod.get("Type", "") in SUPPORTED_MOD_TYPES


def should_skip_description(description: str) -> bool:
    lowered_description = description.lower()
    return "tennokai" in lowered_description


def get_set_name(mod: dict[str, Any]) -> str | None:
    set_label = str(mod.get("Set", "")).strip()
    if not set_label:
        return None
    return re.sub(r"\s+set$", "", set_label, flags=re.IGNORECASE)


def get_compatible_weapons(mod: dict[str, Any]) -> list[str]:
    mod_type = str(mod.get("Type", "")).strip()
    if "Only compatible with Semi-Auto Trigger" in mod.get("Description", ""):
        return MOD_COMPATIBILITY_MAP.get(f"Semi-{mod_type}", "")
    return MOD_COMPATIBILITY_MAP.get(mod_type, "")


def has_effective_stats(record: Stats) -> bool:
    metadata_keys = {"max_rank", "compatible_weapons"}
    return any(key not in metadata_keys for key in record)


def parse_line_stats(stat_description: str, max_rank: int) -> Stats:
    if lock_stat := extract_locks(stat_description.lower()):
        return lock_stat

    bonus_values, stat_text = parse_stat_line(stat_description, max_rank)
    if bonus_values is None or stat_text is None:
        return {}

    parsed_stat: Stats = {}
    if damage_dist := extract_damage_distribution(stat_text, bonus_values):
        parsed_stat["damage_dist"] = damage_dist

    parsed_stat.update(extract_primary_stat(stat_text, bonus_values))
    parsed_stat.update(extract_locks(stat_text))
    return apply_conditions(parsed_stat, stat_description)


def build_mod_record(name: str, mod: dict[str, Any], data: dict[str, Any]) -> Stats | None:
    if not is_supported_mod(mod):
        return None

    description_raw = mod.get("Description", "")
    if should_skip_description(description_raw):
        return None

    set_name = get_set_name(mod)
    description_lines = split_stat_descriptions(description_raw)
    max_rank = mod.get("MaxRank", 0)

    record: Stats = {}
    apply_set_bonus(name, set_name, max_rank, record)

    for stat_description in description_lines:
        parsed_stat = parse_line_stats(stat_description, max_rank)
        if parsed_stat:
            merge_stats(record, parsed_stat)

    if not has_effective_stats(record):
        return None

    record["max_rank"] = max_rank
    record["compatible_weapons"] = get_compatible_weapons(mod)

    return record


def build_mods_json() -> dict[str, dict]:
    mods_raw = load_wiki_records("mods", "Mods")
    mods, _ = collect_records(
        mods_raw,
        lambda name, mod: build_mod_record(name, mod, mods_raw),
        "skipped mods:",
        lambda name, mod: (
            f"{name:<30} {mod.get('Type', 'None'):<10} {repr(mod.get('Description', '') or 'None')}"
            if is_supported_mod(mod)
            else None
        ),
    )

    for mod in mods.values():
        if "damage_dist" in mod and not mod["damage_dist"]:
            del mod["damage_dist"]

    print(f"generated_mods={len(mods)}")
    return mods


def main() -> None:
    write_json_file(OUTPUT_PATHS["mods"], build_mods_json())


if __name__ == "__main__":
    main()
