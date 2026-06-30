from typing import Any

from builder_helpers import (
    OUTPUT_PATHS,
    Stats,
    collect_records,
    load_wiki_records,
    merge_stats,
    normalize_damage_keys,
    write_json_file,
)

STAT_MAP = {
    "CritChance": "crit_chance",
    "CritMultiplier": "crit_damage",
    "Damage": "damage_dist",
    "FireRate": "attack_speed",
    "StatusChance": "status_chance"
}

def extract_primary_stat(attack: dict[str, Any]) -> Stats:
    if attack["AttackName"] != "Normal Attack":
        return {}

    stats = {key: attack[pattern] for pattern, key in STAT_MAP.items() if pattern in attack}
    if "damage_dist" in stats and isinstance(stats["damage_dist"], dict):
        stats["damage_dist"] = normalize_damage_keys(stats["damage_dist"])

    return stats


def build_melee_record(name: str, melee: dict[str, Any]):
    record: Stats = {}
    for attack in melee.get("Attacks", []):
        stats = extract_primary_stat(attack)
        merge_stats(record, stats)

    if not record:
        return None

    record["weapon_type"] = [str(melee.get("Class", "Melee")).strip() or "Melee"]
    return record


def build_melees_json() -> dict[str, dict]:
    melee_data = load_wiki_records("melee")
    melees, _ = collect_records(
        melee_data,
        build_melee_record,
        "skipped melees:",
        lambda name, melee: f"{name:<30} {melee.get('Class', 'None'):<20}",
    )
    print(f"generated_melees={len(melees)}")
    return melees


def main() -> None:
    write_json_file(OUTPUT_PATHS["melees"], build_melees_json())


if __name__ == "__main__":
    main()
