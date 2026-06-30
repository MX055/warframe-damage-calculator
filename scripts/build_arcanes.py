import re
from typing import Any

from builder_helpers import OUTPUT_PATHS, Stats, collect_records, load_wiki_records, merge_stats, write_json_file

ALLOWED_ARCANE_TYPES = {"primary", "secondary", "melee"}

STACKS_RE = re.compile(r"Stacks?\s+up\s+to\s+(\d+)x\b", re.I)
PERCENT_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
MULTIPLIER_RE = re.compile(r"\bx\s*([+-]?\d+(?:\.\d+)?)\b", re.I)

STAT_PATTERNS = [
    (re.compile(r"weak\s*point\s*damage|headshot\s*multiplier|headshot\s*damage", re.I), "weakpoint_damage"),
    (re.compile(r"critical chance", re.I), "crit_chance"),
    (re.compile(r"critical damage", re.I), "crit_damage"),
    (re.compile(r"status chance", re.I), "status_chance"),
    (re.compile(r"reload speed", re.I), "reload_speed"),
    (re.compile(r"multishot", re.I), "multishot"),
    (re.compile(r"fire rate", re.I), "fire_rate"),
]

PERCENT_DAMAGE_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%\s+damage\b", re.I)

RankValues = list[float]


def rank_series(max_value: float, max_rank: int, *, round_digits: int = 3) -> RankValues:
    levels = max_rank + 1
    if levels <= 0:
        return []
    step = max_value / levels
    return [round(step * (i + 1), round_digits) for i in range(levels)]


def split_description_lines(description: str) -> list[str]:
    text = str(description or "")
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    return [line.strip() for line in text.split("\n") if line.strip()]


def parse_line_numbers(line: str) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    for match in PERCENT_RE.finditer(line):
        values.append((match.start(), float(match.group(1)) / 100.0))
    for match in MULTIPLIER_RE.finditer(line):
        values.append((match.start(), float(match.group(1)) - 1.0))
    return values


def nearest_value(stat_index: int, values: list[tuple[int, float]]) -> float | None:
    if not values:
        return None
    return min(values, key=lambda item: abs(item[0] - stat_index))[1]


def extract_line_stats(line: str, max_rank: int, arcane_name: str) -> Stats:
    stats: Stats = {}
    values = parse_line_numbers(line)

    # Secondary Enervate scales by number of qualifying crits, not a percentage rank series.
    if arcane_name == "Secondary Enervate":
        stats["secondary_enervate"] = [rank + 1 for rank in range(max_rank + 1)]
        return stats
    elif arcane_name == "Melee Duplicate":
        stats["melee_duplicate"] = [0.25 + rank*0.15 for rank in range(max_rank + 1)]
    elif arcane_name == "Melee Doughty":
        stats["staking_crit_damage"] = [0.5 + rank*0.1 for rank in range(max_rank + 1)]
        stats["max_stacks"] = None
    elif arcane_name == "Melee Animosity":
        pass
    else:
        for pattern, stat_key in STAT_PATTERNS:
            for match in pattern.finditer(line):
                value = nearest_value(match.start(), values)
                if value is None:
                    continue

                # Keep existing behavior for this arcane output shape.
                if arcane_name == "Secondary Outburst" and stat_key == "crit_chance":
                    continue

                stats[stat_key] = rank_series(value, max_rank)

        if percent_damage := PERCENT_DAMAGE_RE.search(line):
            stats["base_damage"] = rank_series(float(percent_damage.group(1)) / 100.0, max_rank)

        if stacks := STACKS_RE.search(line):
            stack_count = int(stacks.group(1))
            stacked: Stats = {f"stack_{key}": value for key, value in stats.items()}
            stacked["max_stacks"] = stack_count
            return stacked

    return stats


def is_supported_arcane(arcane: dict[str, Any]) -> bool:
    return str(arcane.get("Type", "")).strip().lower() in ALLOWED_ARCANE_TYPES


def get_compatible_weapons(arcane: dict[str, Any]) -> list[str]:
    arcane_type = str(arcane.get("Type", "")).strip().lower()
    return [arcane_type] if arcane_type in ALLOWED_ARCANE_TYPES else []


def has_effective_stats(record: Stats) -> bool:
    metadata_keys = {"max_rank", "compatible_weapons"}
    return any(key not in metadata_keys for key in record)


def build_arcane_record(name: str, arcane: dict[str, Any]) -> Stats | None:
    if not is_supported_arcane(arcane):
        return None

    description = arcane.get("Description", "")
    max_rank = int(arcane.get("MaxRank", 0))

    record: Stats = {}
    for line in split_description_lines(description):
        line_stats = extract_line_stats(line, max_rank, name)
        merge_stats(record, line_stats)

    if not has_effective_stats(record):
        return None

    record["max_rank"] = max_rank
    record["compatible_weapons"] = get_compatible_weapons(arcane)

    return record


def clean_empty_damage_dist(records: dict[str, Stats]) -> dict[str, Stats]:
    for record in records.values():
        if not record.get("damage_dist"):
            record.pop("damage_dist", None)
    return records


def build_arcanes_json() -> dict[str, dict]:
    arcanes_raw = load_wiki_records("arcane", "Arcanes")
    arcanes, skipped = collect_records(
        arcanes_raw,
        build_arcane_record,
        "skipped arcanes:",
        lambda name, arcane: (
            f"{name:<30} {arcane.get('Type', 'None'):<10} {repr(arcane.get('Description', '') or 'None')}"
            if is_supported_arcane(arcane)
            else None
        ),
    )
    arcanes = clean_empty_damage_dist(arcanes)
    print(f"generated_arcanes={len(arcanes)}")
    print(f"skipped_arcanes={skipped}")
    return arcanes


def main() -> None:
    write_json_file(OUTPUT_PATHS["arcanes"], build_arcanes_json())


if __name__ == "__main__":
    main()
