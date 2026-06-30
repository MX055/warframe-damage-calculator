from typing import Any

from builder_helpers import (
    EXPLOSION_ATTACK_NAMES,
    OUTPUT_PATHS,
    PRIMARY_ATTACK_NAMES,
    Stats,
    collect_records,
    load_wiki_records,
    merge_stats,
    normalize_damage_keys,
    write_json_file,
)

BEAM_EXCEPTIONS = ("Tenet Spirex")
AUTO_ATTACK_NAMES = {"Auto", "Auto Mode", "Full Auto Mode", "Fully Spooled", "Beam"}

STAT_MAP = {
    "CritChance": "crit_chance",
    "CritMultiplier": "crit_damage",
    "Damage": "damage_dist",
    "FireRate": "fire_rate",
    "StatusChance": "status_chance",
    "Multishot": "multishot",
    "Reload": "reload_speed",
    "Magazine": "magazine_capacity"
}


def detect_secondary_type(secondary: dict[str, Any]) -> str | None:
    trigger_text = str(secondary.get("Trigger", "")).strip().lower()

    if trigger_text:
        auto_text = trigger_text.replace("semi-auto", "").replace("mag burst", "")
        if "auto" in auto_text or "held" in auto_text:
            return "auto"
        if "burst" in trigger_text:
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


def build_weapon_types(secondary: dict[str, Any]) -> list[str]:
    weapon_class = str(secondary.get("Class", "primary")).strip().lower() or "primary"
    weapon_types = ["secondary", weapon_class]
    if secondary_type := detect_secondary_type(secondary):
        weapon_types.append(f"{secondary_type}-{weapon_class}")
    return weapon_types


def extract_secondary_stat(attack: dict[str, Any]) -> Stats:
    attack_name = attack.get("AttackName")
    if attack_name in PRIMARY_ATTACK_NAMES:
        stats = {key: attack[pattern] for pattern, key in STAT_MAP.items() if pattern in attack}
        if "damage_dist" in stats and isinstance(stats["damage_dist"], dict):
            stats["damage_dist"] = normalize_damage_keys(stats["damage_dist"])
        return stats
    if attack_name in EXPLOSION_ATTACK_NAMES:
        explosion_damage_dist = attack["Damage"]
        if isinstance(explosion_damage_dist, dict):
            explosion_damage_dist = normalize_damage_keys(explosion_damage_dist)
        return {"explosion_damage_dist": explosion_damage_dist}
    return {}


def build_secondary_record(name: str, secondary: dict[str, Any]) -> Stats | None:
    record: Stats = {}
    for attack in secondary.get("Attacks", []):
        stats = extract_secondary_stat(attack)
        merge_stats(record, stats)

    # Some weapons store reload/magazine at the weapon level, not per attack.
    for source_key in ("Reload", "Magazine"):
        target_key = STAT_MAP[source_key]
        if target_key not in record and source_key in secondary:
            record[target_key] = secondary[source_key]

    tags = secondary.get("CompatibilityTags", [])
    record["is_beam"] = "BEAM" in tags if name not in BEAM_EXCEPTIONS else False
    record["weapon_type"] = build_weapon_types(secondary)

    return record or None


def build_secondaries_json() -> dict[str, dict]:
    secondary_data = load_wiki_records("secondary")
    secondaries, _ = collect_records(
        secondary_data,
        build_secondary_record,
        "skipped secondaries:",
        lambda name, secondary: f"{name:<30} {secondary.get('Class', 'None'):<20}",
    )
    print(f"generated_secondaries={len(secondaries)}")
    return secondaries


def main() -> None:
    write_json_file(OUTPUT_PATHS["secondaries"], build_secondaries_json())


if __name__ == "__main__":
    main()