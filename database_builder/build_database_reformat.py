import json
import re
from pathlib import Path

# mypy: disable-error-code="var-annotated,assignment"
from typing import Any

# ----------------------------
# Paths
# ----------------------------

ROOT = Path(__file__).resolve().parent
ITEMS_PATH = ROOT / "raw_data" / "overframe_items.json"
UPGRADES_PATH = ROOT / "raw_data" / "overframe_upgrades.json"

DATABASE_DIR = ROOT.parent / "warframe_damage_calculator" / "data" / "database"
OUT_WEAPONS = DATABASE_DIR / "weapons.json"
OUT_UPGRADES = DATABASE_DIR / "upgrades.json"
OUT_REPORT = ROOT / "reformat_report.json"

BUILDER_VERSION = "v18"


# ----------------------------
# Constants
# ----------------------------

DAMAGE_TYPES = [
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
]

DT_TO_DAMAGE = {
    "DT_IMPACT": "impact",
    "DT_PUNCTURE": "puncture",
    "DT_SLASH": "slash",
    "DT_EXPLOSION": "blast",
    "DT_BLAST": "blast",
    "DT_CORROSIVE": "corrosive",
    "DT_GAS": "gas",
    "DT_MAGNETIC": "magnetic",
    "DT_RADIATION": "radiation",
    "DT_RADIANT": "radiation",
    "DT_VIRAL": "viral",
    "DT_FREEZE": "cold",
    "DT_COLD": "cold",
    "DT_ELECTRICITY": "electricity",
    "DT_FIRE": "heat",
    "DT_HEAT": "heat",
    "DT_POISON": "toxin",
    "DT_TOXIN": "toxin",
}

UPGRADE_TYPE_TO_STAT = {
    # Damage
    "WEAPON_DAMAGE_AMOUNT": "base_damage",
    "WEAPON_MELEE_DAMAGE": "base_damage",
    "WEAPON_DAMAGE_IF_VICTIM_PROC_ACTIVE": "base_damage",
    "WEAPON_DAMAGE_PER_ACTIVE_PROC_STACK_ON_VICTIM": "base_damage",
    "WEAPON_INIT_DAMAGE_MOD": "primed_chamber",
    "WEAPON_FACTION_DAMAGE": "faction_damage",
    "WEAPON_DAMAGE_WEAKPOINT": "weakpoint_damage",
    "WEAPON_HEADSHOT_MULTIPLIER": "weakpoint_damage",
    "WEAPON_HEADSHOT_DAMAGE": "weakpoint_damage",
    # Speed / handling
    "WEAPON_FIRE_RATE": "fire_rate",
    "WEAPON_RELOAD_SPEED": "reload_speed",
    "WEAPON_CLIP_MAX": "magazine_capacity",
    "WEAPON_AMMO_EFFICIENCY": "ammo_efficiency",
    # Multishot
    "WEAPON_FIRE_ITERATIONS": "multishot",
    # Crit
    "WEAPON_CRIT_CHANCE": "crit_chance",
    "WEAPON_CRIT_CHANCE_WEAKPOINT": "weakpoint_crit_chance",
    "WEAPON_CRIT_CHANCE_BODY_PART": "weakpoint_crit_chance",
    "WEAPON_CRIT_DAMAGE": "crit_damage",
    # Status
    "WEAPON_PROC_CHANCE": "status_chance",
    "WEAPON_PROC_DAMAGE": "status_damage",
    "WEAPON_STATUS_DAMAGE": "status_damage",
    # Special calculator mechanics
    "WEAPON_SLASH_PROC_ON_CRIT_CHANCE": "hunter_munitions",
    "WEAPON_PROC_ON_PROC_CHANCE": "secondary_encumber",
}

# Internal quality constants. In this export, Value is usually the per-rank-0 increment.
# Example: Serration Value=0.15 and QA_VERY_HIGH => 0.15 * (10 + 1) = 1.65.
FUSION_LIMIT_TO_MAX_RANK = {
    None: 5,  # normal 5-rank mods often omit FusionLimit
    "QA_NONE": 0,
    "QA_LOW": 0,
    "QA_MEDIUM": 3,  # 60/60 mods, Hammer Shot, starter mods
    "QA_HIGH": 5,  # arcanes
    "QA_VERY_HIGH": 10,  # Serration, primed, galvanized
}

PRIMARY_COMPAT = ["primary", "rifle", "bow", "shotgun", "sniper"]

STANDARD_COMPAT = {"primary", "rifle", "bow", "shotgun", "sniper", "secondary", "pistol", "melee"}
PRIMARY_FAMILY = {"primary", "rifle", "bow", "shotgun", "sniper"}
SECONDARY_FAMILY = {"secondary", "pistol"}
MELEE_FAMILY = {"melee"}

# Modular Kitgun chambers are not complete weapons by themselves. Their final
# stats depend on the grip and loader, so exporting them as standalone weapons
# produces empty damage/fire-cycle data and invalid calculator results.
INCOMPLETE_MODULAR_WEAPONS = {
    "catchmoon",
    "rattleguts",
    "sporelacer",
    "tombfinger",
}

# Upgrade CompatibilityTags that represent extra weapon requirements beyond
# broad compatibility. These are exported in a separate `requirements` object
# instead of being expanded into compatibility combinations.
TRIGGER_COMPAT_TAGS = {
    "SEMI_AUTO": "semi",
}

REQUIREMENT_COMPAT_TAGS = {
    "BEAM": ("is_beam", True),
}


# ----------------------------
# Generic helpers
# ----------------------------


def load_json(path: Any) -> Any:
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return raw


def round_for_output(value: Any) -> Any:
    """Round all numeric calculator values to 3 decimals before writing JSON.

    JSON does not preserve trailing zeroes, so 1.100 is written as 1.1,
    but every float is still rounded to at most 3 decimal places.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, list):
        return [round_for_output(v) for v in value]
    if isinstance(value, dict):
        return {k: round_for_output(v) for k, v in value.items()}
    return value


def save_json(path: Any, data: Any) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(round_for_output(data), f, indent=4, ensure_ascii=False)
        f.write("\n")


def clean_name(value: Any) -> Any:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalized_key(value: Any) -> Any:
    return clean_name(value).casefold()


def zero_damage_dict() -> Any:
    return dict.fromkeys(DAMAGE_TYPES, 0)


def compact_damage_dict(values: Any) -> Any:
    """Drop zero-valued damage/proc entries after the final rounding pass.

    This keeps weapon damage and forced-proc mappings compact while preserving
    any small non-zero value that survives output rounding.
    """
    compact = {}
    for key, value in (values or {}).items():
        if isinstance(value, bool):
            if value:
                compact[key] = value
            continue
        try:
            numeric = float(value or 0)
        except (TypeError, ValueError):
            compact[key] = value
            continue
        if round(numeric, 3) != 0:
            compact[key] = value
    return compact


def add_stat(target: Any, key: Any, value: Any) -> Any:
    if not key or value == 0:
        return
    target[key] = round(float(target.get(key, 0)) + float(value), 6)


def state_block(behavior: Any) -> Any:
    for key, value in behavior.items():
        if key.startswith("state:") and key != "state:Type" and isinstance(value, dict):
            return value
    return {}


def fire_block(behavior: Any) -> Any:
    for key, value in behavior.items():
        if key.startswith("fire:") and key != "fire:Type" and isinstance(value, dict):
            return value
    return {}


def impact_block(behavior: Any) -> Any:
    for key, value in behavior.items():
        if key.startswith("impact:") and key != "impact:Type" and isinstance(value, dict):
            return value
    return {}


def is_alt_behavior(behavior: Any) -> Any:
    return bool(state_block(behavior).get("IsAlternateFire", 0))


def choose_main_behavior(behaviors: Any) -> Any:
    if not behaviors:
        return {}
    non_alt = [b for b in behaviors if not is_alt_behavior(b)]
    if not non_alt:
        return behaviors[0]

    # Prefer the first true base fire mode. Some Incarnon/evolution modes appear as non-alt
    # but have a BehaviorTag pointing at a mod/evolution unlock.
    for behavior in non_alt:
        tag_text = " ".join(str(x) for x in state_block(behavior).values())
        if "Zariman" not in tag_text and "AltFireUnlock" not in tag_text:
            return behavior

    return non_alt[0]


def total_attack_amount(attack_data: Any) -> Any:
    return float(attack_data.get("Amount") or 0)


def projectile_candidates(behavior: Any) -> Any:
    f = fire_block(behavior)
    candidates = []

    # For charged weapons, the charged projectile is usually the useful calculator default.
    for key in ("chargedProjectileType", "projectileType"):
        value = f.get(key)
        if isinstance(value, dict):
            candidates.append(value)

    return candidates


def choose_attack_source(behavior: Any) -> Any:
    candidates = projectile_candidates(behavior)
    if candidates:
        # Prefer the candidate with the highest direct damage.
        # This handles charged/uncharged weapons without needing a multi-mode schema.
        return max(candidates, key=lambda p: total_attack_amount(p.get("AttackData") or {}))

    return impact_block(behavior)


def parse_attack_damage(attack_data: Any) -> Any:
    result = zero_damage_dict()
    if not isinstance(attack_data, dict):
        return result

    amount = float(attack_data.get("Amount") or 0)
    if amount == 0:
        return result

    raw_damage_values = {}
    for dt_key, stat_key in DT_TO_DAMAGE.items():
        if dt_key in attack_data:
            raw_damage_values[stat_key] = raw_damage_values.get(stat_key, 0.0) + float(attack_data.get(dt_key) or 0)

    raw_total = sum(raw_damage_values.values())

    if raw_total > 0:
        # Old format stores physical distribution as fractions. New format stores damage amounts.
        if raw_total <= 1.00001 and amount > 1:
            for stat_key, fraction in raw_damage_values.items():
                result[stat_key] = round(amount * fraction, 6)
        else:
            for stat_key, value in raw_damage_values.items():
                result[stat_key] = round(value, 6)
        return result

    # Element-only attacks often only provide Type + Amount.
    type_key = attack_data.get("Type")
    element_stat = DT_TO_DAMAGE.get(type_key) if isinstance(type_key, str) else None
    if element_stat:
        result[element_stat] = round(amount, 6)

    return result


def parse_status_chance(*attack_datas: Any) -> Any:
    chances = [float(attack_data.get("ProcChance") or 0) for attack_data in attack_datas if isinstance(attack_data, dict) and attack_data.get("ProcChance") is not None]
    return round(max(chances) if chances else 0, 6)


def attack_damage_with_radial_fallback(attack_data: Any) -> Any:
    """Parse attack damage and treat typeless radial Amount as Blast."""
    parsed = parse_attack_damage(attack_data)
    if not any(parsed.values()) and float(attack_data.get("Amount") or 0) > 0:
        # Many radial attacks omit Type in the export; Warframe treats these
        # generic radial explosions as Blast for calculator purposes.
        parsed["blast"] = round(float(attack_data.get("Amount") or 0), 6)
    return parsed


def nonzero_damage_types(values: Any) -> Any:
    return {key for key, value in (values or {}).items() if round(float(value or 0), 6) != 0}


def radial_attack_datas(source: Any) -> Any:
    """Return radial attack entries without double-counting internal embed attacks.

    Many projectiles expose both ExplosiveAttack and EmbedDeathAttack. When both
    describe the same radial damage event, adding both inflates the radial damage
    (Acceltra, Acceltra Prime, Astilla, Penta, Ogris, etc.).

    The useful rule is:
      - use ExplosiveAttack when it contains the player-facing radial damage;
      - use EmbedDeathAttack only when ExplosiveAttack is missing/empty;
      - include both only when they clearly represent different damage stages
        with disjoint damage types, e.g. Lenz's Cold field plus later Blast.
    """
    raw_explosive = source.get("ExplosiveAttack")
    raw_embed_death = source.get("EmbedDeathAttack")
    explosive = raw_explosive if isinstance(raw_explosive, dict) else None
    embed_death = raw_embed_death if isinstance(raw_embed_death, dict) else None

    if explosive is None and embed_death is None:
        return []
    if explosive is not None and embed_death is None:
        return [explosive]
    if embed_death is not None and explosive is None:
        return [embed_death]

    assert explosive is not None and embed_death is not None
    explosive_damage = attack_damage_with_radial_fallback(explosive)
    embed_damage = attack_damage_with_radial_fallback(embed_death)

    explosive_types = nonzero_damage_types(explosive_damage)
    embed_types = nonzero_damage_types(embed_damage)

    if not explosive_types and embed_types:
        return [embed_death]
    if explosive_types and not embed_types:
        return [explosive]
    if not explosive_types and not embed_types:
        return [explosive]

    if explosive_types.isdisjoint(embed_types):
        return [explosive, embed_death]

    return [explosive]


def parse_explosion_damage(source: Any) -> Any:
    result = zero_damage_dict()
    status_chances = []

    for attack_data in radial_attack_datas(source):
        parsed = attack_damage_with_radial_fallback(attack_data)
        for stat_key, value in parsed.items():
            add_stat(result, stat_key, value)
        if attack_data.get("ProcChance") is not None:
            status_chances.append(float(attack_data.get("ProcChance") or 0))

    # Some projectiles contain submunitions. The schema has only one explosion slot, so
    # aggregate their radial contribution instead of dropping it. The same
    # ExplosiveAttack-over-EmbedDeathAttack rule avoids double-counting.
    cluster = source.get("ClusterProjectiles")
    if isinstance(cluster, dict):
        for attack_data in radial_attack_datas(cluster):
            parsed = attack_damage_with_radial_fallback(attack_data)
            for stat_key, value in parsed.items():
                add_stat(result, stat_key, value)
            if attack_data.get("ProcChance") is not None:
                status_chances.append(float(attack_data.get("ProcChance") or 0))

    return result, round(max(status_chances) if status_chances else 0, 6)


def direct_status_chance(source_attack: Any, fallback_attack: Any = None) -> Any:
    """Prefer the chosen attack source's ProcChance and only use fallback if absent."""
    if isinstance(source_attack, dict) and source_attack.get("ProcChance") is not None:
        return parse_status_chance(source_attack)
    return parse_status_chance(fallback_attack)


def trigger_from_behavior(behavior: Any) -> Any:
    state_type = str(behavior.get("state:Type", ""))
    loc_tag = str(state_block(behavior).get("LocTag", ""))
    text = f"{state_type} {loc_tag}".lower()

    if "beam" in text or "continous" in text or "continuous" in text:
        return "held"
    if "charge" in text:
        return "charge"
    if "burst" in text:
        return "burst"
    # Check semi before auto because strings like "semiautomatic" contain "automatic".
    if "semi" in text:
        return "semi"
    if "automatic" in text or "auto" in text:
        return "auto"
    return "unknown"


def weapon_type_from_categories(categories: Any, fallback_product_category: Any = "") -> Any:
    categories = categories or []

    for category in categories:
        if category.startswith("primary-"):
            return category.replace("primary-", "", 1)
        if category.startswith("melee-"):
            return category.replace("melee-", "", 1)

    product = fallback_product_category.casefold()
    if "pistol" in product:
        return "pistol"
    if "longgun" in product or "longguns" in product:
        return "rifle"
    if "melee" in product:
        return "melee"

    return "unknown"


def parse_weapon(path: Any, item: Any) -> Any:
    categories = item.get("categories") or []
    data = item.get("data") or {}
    product_category = data.get("ProductCategory")

    if product_category == "LongGuns":
        section = "primary"
    elif product_category == "Pistols":
        section = "secondary"
    elif product_category == "Melee":
        section = "melee"
    else:
        return None, None

    name = clean_name(item.get("name"))
    if not name:
        return None, None
    if normalized_key(name) in INCOMPLETE_MODULAR_WEAPONS:
        return None, None

    # ProductCategory alone includes abstract base classes and placeholders such as
    # PRIMARY, Pistol, Bow, Rifle, Melee, and other non-equippable templates.
    # The Overframe item export marks real player-facing weapons with the
    # generic category "weapon"; require it so those templates are excluded.
    if "weapon" not in categories:
        return None, None

    behavior = choose_main_behavior(data.get("Behaviors") or [])
    state = state_block(behavior)
    fire = fire_block(behavior)
    impact = impact_block(behavior)
    source = choose_attack_source(behavior)
    source_attack = source.get("AttackData") or impact.get("AttackData") or {}

    # For projectiles, crit/status may live on the projectile; for traces/beams it lives on impact.
    crit_chance = source.get("CriticalChance", impact.get("criticalHitChance", 0))
    crit_damage = source.get("CriticalMultiplier", impact.get("criticalHitDamageMultiplier", 1))

    explosion_damage, explosion_status = parse_explosion_damage(source)

    fire_rate = round(float(state.get("fireRate") or 0) / 60, 6)
    multishot = float(fire.get("fireIterations") or 1)
    magazine = int(data.get("AmmoClipSize") or 0)
    reload_speed = float(state.get("reloadTime") or 0)

    common = {
        "crit_chance": round(float(crit_chance or 0), 6),
        "crit_damage": round(float(crit_damage or 1), 6),
        "status_chance": direct_status_chance(source_attack, impact.get("AttackData")),
        "type": weapon_type_from_categories(categories, str(product_category or "")),
        "damage": parse_attack_damage(source_attack),
        "forced_procs": dict.fromkeys(DAMAGE_TYPES, 0),
    }

    if section in ("primary", "secondary"):
        common.update(
            {
                "multishot": round(multishot, 6),
                "fire_rate": fire_rate,
                "reload_speed": round(reload_speed, 6),
                "magazine_capacity": magazine,
                "weakpoint_damage": 3,
                "recharge_rate": round(float(data.get("BatteryRegenRate") or 0), 6),
                "charge_time": round(float(state.get("ChargeTime") or 0), 6),
                "burst_count": int(state.get("NumShots") or 1),
                "burst_delay": round(float(state.get("BurstDelay") or 0), 6),
                "is_beam": bool("Beam" in str(behavior.get("fire:Type", "")) or "BEAM" in (data.get("CompatibilityTags") or []) or trigger_from_behavior(behavior) == "held"),
                "is_battery": bool(data.get("ClipIsBattery", 0)),
                "trigger": trigger_from_behavior(behavior),
                "explosion_damage": explosion_damage,
                "explosion_forced_procs": dict.fromkeys(DAMAGE_TYPES, 0),
            }
        )

        # Preserve explosion proc chance only when it is stronger than the direct proc chance.
        # The requested schema has no separate status chance for radial damage, so this is only
        # reflected indirectly by max(status_chance, explosion_status).
        if explosion_status > float(common["status_chance"]):
            common["status_chance"] = explosion_status

    else:
        common.update(
            {
                "attack_speed": fire_rate,
            }
        )

    for damage_key in (
        "damage",
        "forced_procs",
        "explosion_damage",
        "explosion_forced_procs",
    ):
        raw_damage = common.get(damage_key)
        if isinstance(raw_damage, dict):
            compacted = compact_damage_dict(raw_damage)
            common[damage_key] = compacted
            if not compacted and damage_key != "damage":
                common.pop(damage_key)

    for field_name, default in (
        ("is_beam", False),
        ("is_battery", False),
        ("recharge_rate", 0.0),
        ("charge_time", 0.0),
        ("burst_delay", 0.0),
        ("burst_count", 1),
        ("weakpoint_damage", 3),
    ):
        if common.get(field_name) == default:
            common.pop(field_name, None)

    return section, common


# ----------------------------
# Upgrade parsing helpers
# ----------------------------


def max_rank_for(data: Any) -> Any:
    return int(FUSION_LIMIT_TO_MAX_RANK.get(data.get("FusionLimit"), 5))


def scaled_value(value: Any, max_rank: Any) -> Any:
    return round(float(value or 0) * (max_rank + 1), 6)


def unscaled_value(value: Any) -> Any:
    return round(float(value or 0), 6)


def stat_from_upgrade(upgrade: Any, compatibility: Any) -> Any:
    raw_upgrade_type = upgrade.get("UpgradeType")
    if not isinstance(raw_upgrade_type, str):
        return None
    upgrade_type = raw_upgrade_type

    if upgrade_type == "WEAPON_PERCENT_BASE_DAMAGE_ADDED":
        damage_type = upgrade.get("DamageType")
        return DT_TO_DAMAGE.get(damage_type) if isinstance(damage_type, str) else None

    stat = UPGRADE_TYPE_TO_STAT.get(upgrade_type)

    # Melee attack speed uses the same internal type as gun fire rate.
    if stat == "fire_rate" and "melee" in compatibility and not any(c in compatibility for c in ("primary", "rifle", "bow", "shotgun", "sniper", "secondary", "pistol")):
        return "attack_speed"

    # Some weakpoint crit bonuses are intended as multiplicative weakpoint crit chance.
    if upgrade_type == "WEAPON_CRIT_CHANCE_WEAKPOINT":
        return "multiplicative_weakpoint_crit_chance"

    return stat


def _condition_label_from_text(text: Any) -> Any:
    compact = re.sub(r"[^a-z0-9]+", "", text.casefold())

    # Order matters: more specific conditions must come before generic ones.
    tests = [
        ("headshot kill", ("onweakpointkill", "weakpointkill", "headshotkill", "onheadshotkill")),
        ("headshot on eximus", ("onheadshoteximus", "headshoteximus")),
        ("headshot", ("onweakpointhit", "weakpointhit", "onheadshot", "headshot", "weakpoint", "symbolfilterhead")),
        ("shield break", ("onshieldbreak", "shieldbreak")),
        ("roll", ("onrollended", "onrollcondition", "rollcondition", "onroll", "rolling")),
        ("land after bullet jump", ("onlandafterspecialjump", "landafterspecialjump", "specialjump")),
        ("wall latch", ("whilewalllatching", "twosecondswalllatch", "walllatch", "walllatching")),
        ("downed enemy", ("ccdownedenemy", "downedenemy")),
        ("invisible", ("pmcloak", "cloak", "invisible", "invisibility")),
        ("heavy attack", ("pmheavymelee", "heavymelee", "heavyattack")),
        ("slide", ("ccsliding", "slideattack", "sliding", "slide")),
        ("lifted enemy", ("ptlifthit", "statuschanceonlifted", "lifted")),
        ("puncture proc", ("puncturestatus", "dtpuncture")),
        ("impact proc", ("impactproc", "dtimpact")),
        ("heat proc", ("heatproc", "dtfire", "dtheat")),
        ("cold proc", ("coldproc", "freezestack", "ptchilled", "dtfreeze", "dtcold")),
        ("electricity proc", ("electricityproc", "electricproc", "ptelectrified", "dtelectricity")),
        ("toxin proc", ("toxinproc", "poisonproc", "ptpoisoned", "dtpoison", "dttoxin")),
        ("status proc", ("onproccondition", "onstatus", "statusproc", "proccondition")),
        ("critical hit", ("oncritcondition", "oncrit", "criticalhit", "critcondition")),
        ("ability cast", ("onability", "abilitycondition", "abilitycast")),
        ("kill", ("onkillcondition", "onkill", "killcondition")),
        ("hit", ("onhitcondition", "onhit", "hitcondition")),
        ("aim", ("pmaim", "whileaiming", "aiming", "aimcondition")),
    ]

    for label, needles in tests:
        if any(needle in compact for needle in needles):
            return label

    return ""


def condition_from_text(data: Any, upgrade: Any = None) -> Any:
    """Best-effort human-readable trigger for conditional upgrade effects.

    Prefer explicit trigger fields (`ConditionTag` / `ConditionalUpgrades`) over
    descriptive stat text (`StatusDescTag`, `LocTag`). This avoids cases where a
    kill-triggered crit-damage-while-aiming buff gets mislabeled as `aim`.
    """
    primary_parts = []
    fallback_parts = []

    value = data.get("ConditionTag")
    if value:
        primary_parts.append(str(value))

    primary_parts.extend(str(value) for value in data.get("ConditionalUpgrades") or [])

    for key in ("EnhancementTag", "StatusDescTag"):
        value = data.get(key)
        if value:
            fallback_parts.append(str(value))

    if upgrade:
        fallback_parts.extend(str(x) for x in (upgrade.get("ValidModifiers") or []))
        fallback_parts.extend(str(x) for x in (upgrade.get("ValidPostures") or []))
        fallback_parts.extend(str(x) for x in (upgrade.get("ValidProcTypes") or []))
        fallback_parts.append(str(upgrade.get("SymbolFilter") or ""))
        fallback_parts.append(str(upgrade.get("LocTag") or ""))

    return _condition_label_from_text(" ".join(primary_parts)) or _condition_label_from_text(" ".join([*primary_parts, *fallback_parts]))


def condition_for_upgrade(data: Any, upgrade: Any = None) -> Any:
    """Prefer item/sub-upgrade trigger metadata over per-stat description text.

    This avoids cases such as Cascadia Accuracy, where the real trigger is
    rolling but the affected stat is headshot/weakpoint crit chance.
    """
    return condition_from_text(data) or condition_from_text({}, upgrade)


def has_condition(data: Any, upgrade: Any = None) -> Any:
    return bool(
        data.get("ConditionalUpgrades")
        or data.get("ConditionTag")
        or data.get("MaxConditionalStacks")
        or (upgrade and (upgrade.get("ValidModifiers") or upgrade.get("ValidPostures") or upgrade.get("ValidProcTypes") or upgrade.get("SymbolFilter")))
    )


def generic_compat_from_text(text: Any) -> Any:
    """Return broad weapon slots/categories mentioned by a path or localization tag."""
    compat = set()

    if "LotusLongGun" in text or "Loadout_LongGun" in text or "/LongGuns/" in text:
        compat.update(PRIMARY_COMPAT)
    if "LotusSniperRifle" in text or "SniperCategoryName" in text or "/Sniper" in text:
        compat.add("sniper")
    if "LotusShotgun" in text or "ShotgunCategoryName" in text or "/Shotgun" in text:
        compat.add("shotgun")
    if "LotusRifle" in text or "RifleCategoryName" in text or "AssaultRifleCategoryName" in text or "RifleNoAoe" in text or "/Rifle/" in text:
        compat.update(["rifle", "bow"])
    if "LotusBow" in text or "BowCategoryName" in text or "/Bows/" in text:
        compat.add("bow")
    if "LotusPistol" in text or "PistolCategoryName" in text or "PistolNoAoe" in text or "/Pistol" in text or "/Pistols/" in text:
        compat.add("pistol")
    if "PlayerMeleeWeapon" in text or "MeleeCategoryName" in text or "Loadout_Melee" in text or "/Melee/" in text:
        compat.add("melee")

    return compat


def install_scope_from_data(data: Any, weapon_path_to_name: Any) -> Any:
    """
    Internal-only install scope. This describes the weapon class the upgrade is
    equipped on, not the weapon class that a conditional effect might buff.

    ValidType is intentionally excluded because mods such as Combo Fury are
    equipped on melee but use ValidType=/Lotus/Weapons/Tenno/Pistol/LotusPistol
    to describe the secondary weapon they buff.
    """
    comp = str(data.get("ItemCompatibility") or "")
    loc = str(data.get("ItemCompatibilityLocTag") or "")
    extra = data.get("ExtraItemCompatibility") or []
    text = " ".join([comp, loc, *(str(x) for x in extra)])

    scope = generic_compat_from_text(text)
    if comp in weapon_path_to_name:
        scope.add(normalized_key(weapon_path_to_name[comp]))
        # Exact paths do not always include a generic ItemCompatibility tag, so
        # derive the broad slot from the path as an internal matching aid.
        scope.update(generic_compat_from_text(comp))

    return scope


def compatibility_from_data(data: Any, item_path: Any, weapon_path_to_name: Any) -> Any:
    comp = str(data.get("ItemCompatibility") or "")

    # Weapon-specific augments should remain exact in the exported database.
    if comp in weapon_path_to_name:
        return [normalized_key(weapon_path_to_name[comp])]

    compat = install_scope_from_data(data, weapon_path_to_name) & STANDARD_COMPAT
    return sorted(compat)


def trigger_restrictions_from_data(data: Any) -> Any:
    tags = data.get("CompatibilityTags") or []
    return {TRIGGER_COMPAT_TAGS[tag] for tag in tags if tag in TRIGGER_COMPAT_TAGS}


def requirements_from_data(data: Any) -> Any:
    """Export additional weapon requirements separately from compatibility.

    Examples:
        {"trigger": ["semi"]}
        {"is_beam": True}
        {"trigger": ["semi"], "is_beam": True}
        []  # no extra requirements
    """
    tags = data.get("CompatibilityTags") or []
    requirements = {}

    triggers = sorted(trigger_restrictions_from_data(data))
    if triggers:
        requirements["trigger"] = triggers

    for tag in tags:
        mapped = REQUIREMENT_COMPAT_TAGS.get(tag)
        if not mapped:
            continue
        key, value = mapped
        requirements[key] = value

    return requirements or {}


def target_scope_from_upgrade(upgrade: Any, weapon_path_to_name: Any) -> Any:
    """
    Scope targeted by an individual Upgrade entry. Empty means it applies to the
    weapon the mod is installed on. Non-empty ValidType values can point to a
    different weapon class, e.g. melee-equipped Combo Fury buffing pistols.
    """
    valid_type = str(upgrade.get("ValidType") or "")
    if not valid_type:
        return set()
    if valid_type in weapon_path_to_name:
        return {normalized_key(weapon_path_to_name[valid_type])}
    return generic_compat_from_text(valid_type)


def scopes_overlap(install_scope: Any, target_scope: Any) -> Any:
    if not target_scope:
        return True
    if install_scope & target_scope:
        return True
    return bool((install_scope & PRIMARY_FAMILY and target_scope & PRIMARY_FAMILY) or (install_scope & SECONDARY_FAMILY and target_scope & SECONDARY_FAMILY) or (install_scope & MELEE_FAMILY and target_scope & MELEE_FAMILY))


def upgrade_targets_installed_weapon(upgrade: Any, install_scope: Any, weapon_path_to_name: Any) -> Any:
    return scopes_overlap(install_scope, target_scope_from_upgrade(upgrade, weapon_path_to_name))


def is_bow_specific_duplicate_bonus(upgrade: Any) -> Any:
    """Return True for raw duplicate bonus entries used for "x2 for bows".

    Some rifle/primary mods store the normal stat once, then store a second
    hidden entry with CheckTypeOnInstall=1 and ValidType=LotusBow. Adding both
    makes the exported database always use the bow x2 value. The calculator
    database should export the normal stat, so these bow-only duplicate entries
    are skipped.
    """
    valid_type = str(upgrade.get("ValidType") or "")
    if not valid_type:
        return False

    if not bool(upgrade.get("CheckTypeOnInstall", 0)):
        return False

    return bool(generic_compat_from_text(valid_type) == {"bow"})


def is_tennokai_upgrade(item_path: Any, item: Any, data: Any) -> Any:
    """Return True for Tenokai / Empowered Heavy Melee mods.

    These are special melee slot mods, not normal calculator weapon mods. In the
    raw export they are identified by the EmpoweredHeavyMelee folder/family,
    the PERFECT_HEAVY_MELEE tip tag, and the Tenokai install sound.
    """
    parents = item.get("parents") or []
    tip_tags = data.get("TipTags") or []
    install_sound = str(data.get("InstallSound") or "")

    if "/EmpoweredHeavyMelee/" in str(item_path):
        return True
    if any("/EmpoweredHeavyMelee/" in str(parent) for parent in parents):
        return True
    if "PERFECT_HEAVY_MELEE" in tip_tags:
        return True
    return "TennokaiModInstall" in install_sound


def is_standard_weapon_upgrade(data: Any, item_path: Any, weapon_path_to_name: Any) -> Any:
    if data.get("AvailableOnPve") == 0:
        return False
    if "/PvPMods/" in item_path:
        return False
    if data.get("IsAbilityAugment"):
        return False

    compatibility = compatibility_from_data(data, item_path, weapon_path_to_name)
    if not compatibility:
        return False

    return bool(set(compatibility) & STANDARD_COMPAT or any(name for name in compatibility if name in {normalized_key(v) for v in weapon_path_to_name.values()}))


def merge_stat_dict(dst: Any, src: Any) -> Any:
    for key, value in src.items():
        add_stat(dst, key, value)


def add_condition(target: Any, stat: Any, condition: Any) -> Any:
    if not stat or not condition:
        return

    existing = target.get(stat)
    if existing is None:
        target[stat] = condition
        return

    if existing == condition:
        return

    if isinstance(existing, list):
        if condition not in existing:
            existing.append(condition)
        return

    target[stat] = [existing, condition]


def merge_condition_dict(dst: Any, src: Any) -> Any:
    for stat, condition in (src or {}).items():
        if isinstance(condition, list):
            for item in condition:
                add_condition(dst, stat, item)
        else:
            add_condition(dst, stat, condition)


def add_default_conditions(conditions: Any, conditionals: Any, default_condition: Any) -> Any:
    for stat in conditionals:
        if stat not in conditions:
            add_condition(conditions, stat, default_condition or "condition")


def parse_upgrade_list(data: Any, compatibility: Any, max_rank: Any, *, upgrade_key: Any, scale_values: Any, force_bucket: Any = None, install_scope: Any = None, weapon_path_to_name: Any = None) -> Any:  # fmt: skip
    stats = {}
    conditionals = {}
    stackables = {}
    conditions = {}

    for upgrade in data.get(upgrade_key) or []:
        stat = stat_from_upgrade(upgrade, compatibility)
        if not stat:
            continue

        if install_scope is not None and weapon_path_to_name is not None and not upgrade_targets_installed_weapon(upgrade, install_scope, weapon_path_to_name):
            continue

        # True Steel / Sacrificial Steel / Galvanized Steel include a second
        # PM_HEAVY_MELEE crit entry in the export. The current calculator schema
        # has no heavy-attack-specific crit field, so treating it as a normal
        # conditional doubles the mod incorrectly.
        if upgrade.get("UpgradeType") == "WEAPON_CRIT_CHANCE" and "PM_HEAVY_MELEE" in (upgrade.get("ValidModifiers") or []):
            continue

        value = scaled_value(upgrade.get("Value"), max_rank) if scale_values else unscaled_value(upgrade.get("Value"))

        # Some fire-rate mods store the normal value once, then store the bow
        # "x2 for bows" part as a second hidden bow-only upgrade. Keep that
        # extra value, but export it as a bow conditional instead of adding it
        # to the unconditional stat bucket.
        if is_bow_specific_duplicate_bonus(upgrade):
            add_stat(conditionals, stat, value)
            add_condition(conditions, stat, "bow")
            continue

        upgrade_type = upgrade.get("UpgradeType")
        is_per_stack_damage = upgrade_type in {
            "WEAPON_DAMAGE_IF_VICTIM_PROC_ACTIVE",
            "WEAPON_DAMAGE_PER_ACTIVE_PROC_STACK_ON_VICTIM",
        }

        if force_bucket == "stats":
            add_stat(stats, stat, value)
        elif force_bucket == "conditionals":
            add_stat(conditionals, stat, value)
            add_condition(conditions, stat, condition_for_upgrade(data, upgrade) or "condition")
        elif force_bucket == "stackables" or is_per_stack_damage:
            add_stat(stackables, stat, value)
            if is_per_stack_damage:
                add_condition(conditions, stat, condition_for_upgrade(data, upgrade))
        elif data.get("MaxConditionalStacks"):
            add_stat(stackables, stat, value)
        elif has_condition(data, upgrade):
            add_stat(conditionals, stat, value)
            add_condition(conditions, stat, condition_for_upgrade(data, upgrade) or "condition")
        else:
            add_stat(stats, stat, value)

    return stats, conditionals, stackables, conditions


def parse_script_specials(data: Any, name: Any, max_rank: Any) -> Any:
    stats = {}
    conditionals = {}
    stackables = {}
    max_stacks_override = 0

    scripts = [data[key] for key in ("Script", "EnhancementTagLocScript") if isinstance(data.get(key), dict)]
    scripts.extend(sub["Script"] for sub in data.get("SubUpgrades") or [] if isinstance(sub, dict) and isinstance(sub.get("Script"), dict))

    for script in scripts:
        script_name = str(script.get("Script") or "")
        mod_proc_type = str(script.get("_modProcType") or "")

        # Internal Bleeding / Hemorrhage style script.
        if mod_proc_type == "WEAPON_SLASH_PROC_ON_IMPACT":
            values = script.get("_baseProcChance")
            if isinstance(values, list) and values:
                conditionals["internal_bleeding"] = round(float(values[min(max_rank, len(values) - 1)]), 6)
            elif script.get("_baseProcChance") is not None:
                conditionals["internal_bleeding"] = round(float(script.get("_baseProcChance")), 6)

        # Secondary Enervate.
        if "CritOnHit.lua" in script_name:
            crit_chance = float(script.get("_critChanceBase") or 0) + float(script.get("_critChancePerLevel") or 0) * max_rank
            reset_count = int((script.get("_numTieredCritsToResetBase") or 0) + (script.get("_numTieredCritToResetPerLevel") or 0) * max_rank)
            if crit_chance:
                conditionals["flat_crit_chance"] = round(crit_chance, 6)
            if reset_count:
                conditionals["secondary_enervate"] = reset_count

        # Melee Exposure style: corrosive per ability cast up to a hard limit.
        if "CorrosiveMeleePerAbilityCast.lua" in script_name:
            damage_type = DT_TO_DAMAGE.get(script.get("_damageUpgradeType"), "corrosive")
            step = float(script.get("_buffStepPerCast") or 0) + float(script.get("_buffStepPerFusionLevel") or 0) * max_rank
            hard_limit = float(script.get("_buffHardLimit") or 0)
            if step:
                stackables[damage_type] = round(step, 6)
            if hard_limit and step:
                max_stacks_override = max(1, round(hard_limit / step))

        # Melee Doughty.
        if "GiveStatForDamageType.lua" in script_name:
            give_stat_type = script.get("_giveStatType")
            if give_stat_type == "WEAPON_CRIT_DAMAGE":
                value = float(script.get("_giveStatIncreaseBase") or 0) + float(script.get("_giveStatIncreasePerLevel") or 0) * max_rank
                conditionals["melee_doughty"] = round(value, 6)

    # Chance-based special arcanes.
    chance = data.get("UpgradeChance")
    chance_scale = data.get("UpgradeChanceScalePerRank")
    chance_at_max = None
    if chance is not None:
        chance_at_max = float(chance or 0) + float(chance_scale or 0) * max_rank
        chance_at_max = round(chance_at_max, 6)

    if normalized_key(name) == "melee duplicate" and chance_at_max is not None:
        conditionals["melee_duplicate"] = chance_at_max

    if normalized_key(name) == "secondary encumber" and chance_at_max is not None and "secondary_encumber" not in conditionals:
        conditionals["secondary_encumber"] = chance_at_max

    if normalized_key(name) == "secondary shiver":
        max_stacks_override = 10

    return stats, conditionals, stackables, max_stacks_override


def parse_sub_upgrades(data: Any, compatibility: Any, install_scope: Any, weapon_path_to_name: Any) -> Any:
    """
    Galvanized mods and some arcanes store their conditional/stacking part as SubUpgrades.
    """
    stats = {}
    conditionals = {}
    stackables = {}
    conditions = {}
    max_stacks = 0
    condition = ""

    for sub in data.get("SubUpgrades") or []:
        if not isinstance(sub, dict):
            continue

        sub_max_rank = max_rank_for(sub)
        sub_condition = condition_from_text(sub)
        if sub_condition and not condition:
            condition = sub_condition

        sub_force_bucket = "stackables" if sub.get("MaxConditionalStacks") else None
        sub_stats, sub_conditionals, sub_stackables, sub_conditions = parse_upgrade_list(
            sub,
            compatibility,
            sub_max_rank,
            upgrade_key="Upgrades",
            scale_values=True,
            force_bucket=sub_force_bucket,
            install_scope=install_scope,
            weapon_path_to_name=weapon_path_to_name,
        )

        merge_stat_dict(stats, sub_stats)
        merge_stat_dict(conditionals, sub_conditionals)
        merge_stat_dict(stackables, sub_stackables)
        merge_condition_dict(conditions, sub_conditions)

        if sub.get("MaxConditionalStacks"):
            max_stacks = max(max_stacks, int(sub.get("MaxConditionalStacks") or 0))

        sp_stats, sp_cond, sp_stack, sp_max_stacks = parse_script_specials(sub, "", sub_max_rank)
        merge_stat_dict(stats, sp_stats)
        merge_stat_dict(conditionals, sp_cond)
        merge_stat_dict(stackables, sp_stack)
        max_stacks = max(max_stacks, sp_max_stacks)

    add_default_conditions(conditions, conditionals, condition)
    return stats, conditionals, stackables, conditions, max_stacks, condition


def add_vigilante_bonus(data: Any, result_stats: Any) -> Any:
    mod_set = str(data.get("ModSet") or "")
    if "Vigilante" in mod_set:
        # Set bonus is 5% chance per Vigilante mod to enhance critical hits.
        result_stats["vigilante_bonus"] = 0.05


def raw_incompatibility_tags(data: Any) -> Any:
    """
    Raw IncompatibilityTags mostly describe weapon restrictions such as
    SENTINEL_WEAPON, HOUND_WEAPON, MODULAR_GUN, NO_AIM, etc.

    The calculator's `incompatibility` field is intended for upgrade-vs-upgrade
    conflicts like Serration / Amalgam Serration / Galvanized variants, so raw
    weapon restriction tags are intentionally not exported here.
    """
    return []


def infer_incompatibility(name: Any, all_names: Any) -> Any:
    """
    The export rarely stores direct mod-name incompatibilities. This conservative
    heuristic groups obvious variants and known direct counterparts, while raw
    IncompatibilityTags are added separately by raw_incompatibility_tags().
    """
    all_name_keys = {normalized_key(n) for n in all_names}
    key_to_name = {}
    for original in all_names:
        key_to_name.setdefault(normalized_key(original), original)

    n = normalized_key(name)

    aliases = {
        # Variants / direct counterparts
        "sacrificial pressure": "pressure point",
        "sacrificial steel": "true steel",
        "berserker fury": "fury",
        "primed chamber": "charged chamber",
        # Galvanized counterparts that cannot be handled by simple prefix stripping.
        "galvanized chamber": "split chamber",
        "galvanized hell": "hell's chamber",
        "galvanized diffusion": "barrel diffusion",
        "galvanized aptitude": "rifle aptitude",
        "galvanized savvy": "shotgun savvy",
        "galvanized shot": "sure shot",
        "galvanized scope": "argon scope",
        "galvanized crosshairs": "hydraulic crosshairs",
        "galvanized steel": "true steel",
        "galvanized elementalist": "melee elementalist",
    }

    prefixes = ("amalgam ", "primed ", "sacrificial ", "archon ")

    def direct_family(mod_name: Any) -> Any:
        if mod_name in aliases and aliases[mod_name] in all_name_keys:
            return aliases[mod_name]

        for prefix in prefixes:
            if mod_name.startswith(prefix):
                stripped = mod_name[len(prefix) :]
                # Only treat it as a variant when the unprefixed base mod exists.
                if stripped in all_name_keys:
                    return stripped

        return None

    my_family = direct_family(n)
    if not my_family and any(direct_family(other) == n for other in all_name_keys):
        # If this is the base mod, include its known variants too.
        my_family = n

    if not my_family:
        return []

    out = []
    for other_key, other_name in key_to_name.items():
        if other_key == n:
            continue
        if other_key == my_family or direct_family(other_key) == my_family:
            out.append(other_name)

    return sorted(set(out), key=normalized_key)


def apply_known_mod_overrides(name: Any, stats: Any, conditionals: Any, stackables: Any, conditions: Any) -> Any:
    """Hard-code effects/condition labels not represented cleanly by the export schema."""
    n = normalized_key(name)

    # Sacrificial set bonus with both Sacrificial mods equipped.
    # The raw export exposes the Sentient faction part, but not the set-bonus
    # calculator value in a clean calculator-friendly way.
    if n == "sacrificial pressure":
        conditionals["base_damage"] = 0.275
        add_condition(conditions, "base_damage", "sacrificial set")
    elif n == "sacrificial steel":
        conditionals["crit_chance"] = 0.55
        add_condition(conditions, "crit_chance", "sacrificial set")

    # Cannonade mods prevent fire-rate modification; Acuity mods prevent multishot.
    if "cannonade" in n:
        stats["fire_rate_lock"] = True
    if "acuity" in n:
        stats["multishot_lock"] = True

    # Script/special cases where the raw export does not expose the condition as
    # a normal Upgrade entry, or where the generic text parser picks the affected
    # stat instead of the actual trigger.
    known_conditions = {
        "internal bleeding": {"internal_bleeding": "impact proc"},
        "hemorrhage": {"internal_bleeding": "impact proc"},
        "secondary enervate": {
            "flat_crit_chance": "hit",
            "secondary_enervate": "hit",
        },
        "secondary encumber": {"secondary_encumber": "status proc"},
        "melee duplicate": {"melee_duplicate": "critical hit"},
        "melee doughty": {"melee_doughty": "puncture proc"},
        "cascadia accuracy": {"weakpoint_crit_chance": "roll"},
        "hunter's bonesaw": {"status_chance": "downed enemy"},
        "spectral serration": {"base_damage": "invisible"},
        "motus setup": {
            "crit_chance": "land after bullet jump",
            "status_chance": "land after bullet jump",
        },
        "proton jet": {
            "crit_chance": "wall latch",
            "status_chance": "wall latch",
        },
        "proton snap": {
            "toxin": "wall latch",
            "status_chance": "wall latch",
        },
        "eximus advantage": {"base_damage": "headshot on eximus"},
        "biotic rounds": {
            "viral": "headshot kill",
            "magnetic": "headshot kill",
            "status_chance": "headshot kill",
        },
    }

    for stat, condition in known_conditions.get(n, {}).items():
        if stat in conditionals:
            conditions[stat] = condition


def parse_upgrade(path: Any, item: Any, weapon_path_to_name: Any, all_upgrade_names: Any) -> Any:
    data = item.get("data") or {}
    name = clean_name(item.get("name"))
    if not name:
        return None, None, None

    categories = item.get("categories") or []
    if "arcane" in categories or item.get("tag") == "RelicsAndArcanes":
        section = "arcane"
    elif "mod" in categories or item.get("tag") == "Mod":
        section = "mod"
    else:
        return None, None, None

    if section == "mod" and is_tennokai_upgrade(path, item, data):
        return None, None, None

    if not is_standard_weapon_upgrade(data, path, weapon_path_to_name):
        return None, None, None

    compatibility = compatibility_from_data(data, path, weapon_path_to_name)
    if not compatibility:
        return None, None, None

    requirements = requirements_from_data(data)

    install_scope = install_scope_from_data(data, weapon_path_to_name)
    max_rank = max_rank_for(data)
    condition = condition_from_text(data)
    if not condition:
        for upgrade in data.get("Upgrades") or []:
            if upgrade.get("UpgradeType") in {
                "WEAPON_DAMAGE_IF_VICTIM_PROC_ACTIVE",
                "WEAPON_DAMAGE_PER_ACTIVE_PROC_STACK_ON_VICTIM",
            }:
                condition = "status proc"
                break

    # Normal Upgrades usually scale by rank.
    stats, conditionals, stackables, conditions = parse_upgrade_list(
        data,
        compatibility,
        max_rank,
        upgrade_key="Upgrades",
        scale_values=True,
        install_scope=install_scope,
        weapon_path_to_name=weapon_path_to_name,
    )

    # ExtraUpgrades are static effects that can unlock at a specific rank.
    # For example, Deadhead's headshot multiplier and Merciless's reload speed
    # only become active at rank 5 and must not be linearly scaled below it.
    ex_stats, ex_cond, ex_stack, ex_conditions = parse_upgrade_list(
        data,
        compatibility,
        max_rank,
        upgrade_key="ExtraUpgrades",
        scale_values=False,
        force_bucket="stats",
        install_scope=install_scope,
        weapon_path_to_name=weapon_path_to_name,
    )
    extra_rank_value = data.get("ExtraUpgradeFusionLevel")
    if extra_rank_value not in FUSION_LIMIT_TO_MAX_RANK:
        raise ValueError(f"Unknown ExtraUpgradeFusionLevel {extra_rank_value!r} for {name!r}")
    extra_required_rank = FUSION_LIMIT_TO_MAX_RANK[extra_rank_value]
    rank_locked_stats = {stat: [value, extra_required_rank] for stat, value in sorted(ex_stats.items())}
    merge_stat_dict(conditionals, ex_cond)
    merge_stat_dict(stackables, ex_stack)
    merge_condition_dict(conditions, ex_conditions)

    sp_stats, sp_cond, sp_stack, max_stacks_override = parse_script_specials(data, name, max_rank)
    merge_stat_dict(stats, sp_stats)
    merge_stat_dict(conditionals, sp_cond)
    merge_stat_dict(stackables, sp_stack)

    sub_stats, sub_cond, sub_stack, sub_conditions, sub_max_stacks, sub_condition = parse_sub_upgrades(data, compatibility, install_scope, weapon_path_to_name)
    merge_stat_dict(stats, sub_stats)
    merge_stat_dict(conditionals, sub_cond)
    merge_stat_dict(stackables, sub_stack)
    merge_condition_dict(conditions, sub_conditions)
    if sub_max_stacks:
        max_stacks_override = max(max_stacks_override, sub_max_stacks)
    if not condition and sub_condition:
        condition = sub_condition

    add_vigilante_bonus(data, stats)
    apply_known_mod_overrides(name, stats, conditionals, stackables, conditions)
    add_default_conditions(conditions, conditionals, condition)

    # Skip utility/exilus mods with no calculator-supported effects.
    if not stats and not conditionals and not stackables:
        return None, None, None

    raw_max_stacks = int(max_stacks_override or data.get("MaxConditionalStacks") or 0)
    max_stacks = raw_max_stacks if raw_max_stacks > 0 else None

    condition_value = condition if conditionals and condition else None

    conditional_stats = {stat: [value, conditions.get(stat, condition_value or "condition")] for stat, value in sorted(conditionals.items())}
    stacking_condition = condition or sub_condition or "stacks"
    stacking_stats = {stat: [value, conditions.get(stat, stacking_condition)] for stat, value in sorted(stackables.items())}

    parsed = {
        "compatibility": compatibility,
        "max_rank": max_rank,
    }
    if requirements:
        parsed["requirements"] = requirements
    if max_stacks is not None:
        parsed["max_stacks"] = max_stacks
    if stats:
        parsed["stats"] = dict(sorted(stats.items()))
    if rank_locked_stats:
        parsed["rank_locked_stats"] = rank_locked_stats
    if conditional_stats:
        parsed["conditional_stats"] = conditional_stats
    if stacking_stats:
        parsed["stacking_stats"] = stacking_stats

    if section == "mod":
        incompatibility = sorted(
            set(infer_incompatibility(name, all_upgrade_names) + raw_incompatibility_tags(data)),
            key=normalized_key,
        )
        if incompatibility:
            parsed["incompatibility"] = incompatibility
        if data.get("IsUtility", 0):
            parsed["is_exilus"] = True

    return section, name, parsed


# ----------------------------
# Main conversion
# ----------------------------


def combine_upgrade_stats(parsed: Any) -> Any:
    """Fold the builder's working buckets into the public effect-list schema."""
    combined = {}

    def add(stat: Any, effect: Any) -> Any:
        current = combined.get(stat)
        if current is None:
            combined[stat] = effect
        elif isinstance(current, list):
            current.append(effect)
        else:
            combined[stat] = [current, effect]

    for stat, value in sorted(parsed.get("stats", {}).items()):
        add(stat, value)
    for stat, pair in sorted(parsed.get("rank_locked_stats", {}).items()):
        value, rank = pair
        add(stat, {"value": value, "when": {"rank": rank}})
    for stat, pair in sorted(parsed.get("conditional_stats", {}).items()):
        value, condition = pair
        add(stat, {"value": value, "when": condition})
    for stat, pair in sorted(parsed.get("stacking_stats", {}).items()):
        value, condition = pair
        add(stat, {"value": value, "when": condition, "stacking": True})

    return dict(sorted(combined.items()))


def build_weapons(items: Any) -> Any:
    weapons = {"primary": {}, "secondary": {}, "melee": {}}

    for path, item in items.items():
        section, parsed = parse_weapon(path, item)
        if section and parsed:
            name = clean_name(item.get("name"))
            context = {"name": name, "category": section}
            context.update({key: parsed.pop(key) for key in ("type", "trigger", "is_beam", "is_battery") if key in parsed})
            weapons[section][name] = {"context": context, "stats": parsed}

    for section in weapons:
        weapons[section] = dict(sorted(weapons[section].items(), key=lambda kv: normalized_key(kv[0])))

    return weapons


def build_upgrades(upgrades: Any, items: Any, weapons: Any) -> Any:
    weapon_path_to_name = {path: clean_name(item.get("name")) for path, item in items.items() if "weapon" in (item.get("categories") or []) and clean_name(item.get("name"))}

    all_upgrade_names = [clean_name(item.get("name")) for item in upgrades.values() if clean_name(item.get("name"))]

    result = {"mod": {}, "arcane": {}}

    for path, item in upgrades.items():
        section, name, parsed = parse_upgrade(path, item, weapon_path_to_name, all_upgrade_names)
        if section and name and parsed:
            context = {"name": name, "category": section}
            context.update(
                {
                    key: parsed.pop(key)
                    for key in (
                        "compatibility",
                        "incompatibility",
                        "requirements",
                        "max_rank",
                        "max_stacks",
                        "is_exilus",
                    )
                    if key in parsed
                }
            )
            defaults = {
                "compatibility": [],
                "incompatibility": [],
                "requirements": {},
                "max_rank": None,
                "max_stacks": None,
                "is_exilus": False,
            }
            context = defaults | context
            result[section][name] = {
                "context": context,
                "stats": combine_upgrade_stats(parsed),
            }

    for section in result:
        result[section] = dict(sorted(result[section].items(), key=lambda kv: normalized_key(kv[0])))

    return result


def preserve_forced_procs(weapons: Any, path: Any) -> Any:
    """Keep wiki-imported forced procs when rebuilding the base database."""
    if not path.exists():
        return weapons

    existing = load_json(path)

    for section, entries in weapons.items():
        old_entries = existing.get(section, {})
        for name, weapon in entries.items():
            old_weapon = old_entries.get(name) or {}
            for field in ("forced_procs", "explosion_forced_procs"):
                values = old_weapon.get("stats", old_weapon).get(field)
                if values:
                    weapon["stats"][field] = values
    return weapons


def report(weapons: Any, upgrades: Any) -> Any:
    return {
        "builder_version": BUILDER_VERSION,
        "weapon_counts": {section: len(entries) for section, entries in weapons.items()},
        "upgrade_counts": {section: len(entries) for section, entries in upgrades.items()},
        "notes": [
            "Records are exported as unified {'context': ..., 'stats': ...} mappings.",
            "Only the main/default fire behavior is exported; alternate fire modes are not represented by the requested schema.",
            "Weapon entries must have the source category 'weapon'; abstract templates/placeholders such as PRIMARY, Pistol, Bow, Rifle, Melee, and ???? are excluded.",
            "Incomplete modular Kitgun chambers (Catchmoon, Rattleguts, Sporelacer, and Tombfinger) are excluded because their final stats depend on other components.",
            "Zero-valued entries are omitted from weapon damage, forced_procs, explosion_damage, and explosion_forced_procs.",
            "Radial/explosion damage is aggregated into explosion_damage when it is present in projectile data.",
            "Forced procs are left empty unless the source schema exposes a reliable forced-proc field.",
            "Direct mod-name incompatibilities are inferred conservatively from obvious variants; raw weapon restriction tags such as sentinel_weapon, hound_weapon, modular_gun, no_aim, and no_attack_speed are intentionally not exported as upgrade incompatibilities.",
            "Upgrade stats combine scalar and effect objects in one stat value or list; conditional objects use {'value': value, 'when': condition}.",
            "Stacking effects add 'stacking': true, and rank locks use a {'rank': required_rank} condition.",
            "Condition detection prefers item/sub-upgrade trigger metadata over affected-stat text to avoid incorrect labels such as roll effects being marked as headshot effects.",
            "Unsupported utility stats such as recoil, projectile speed, ammo mutation, zoom, punch-through, and parkour are filtered out because they are not in the requested calculator stat list.",
            "Upgrade entries whose ValidType targets another weapon slot are ignored; if that leaves an upgrade with no calculator-supported on-weapon effects, the upgrade is removed.",
            "Trigger-restricted upgrades keep broad compatibility and export extra restrictions in requirements, e.g. {'trigger': ['semi']} or {'is_beam': true}; empty requirements are omitted.",
            "Tenokai / Empowered Heavy Melee mods are excluded because they use a special slot/mechanic that is not represented by the calculator's normal weapon mod schema.",
            "Bow-only duplicate bonus entries used for raw '(x2 for bows)' display are exported as conditional effects with condition 'bow'.",
        ],
    }


def main() -> Any:
    items = load_json(ITEMS_PATH)
    upgrades = load_json(UPGRADES_PATH)

    weapons_out = build_weapons(items)
    weapons_out = preserve_forced_procs(weapons_out, OUT_WEAPONS)
    upgrades_out = build_upgrades(upgrades, items, weapons_out)

    save_json(OUT_WEAPONS, weapons_out)
    save_json(OUT_UPGRADES, upgrades_out)
    # save_json(OUT_REPORT, report(weapons_out, upgrades_out))

    print("Wrote:")
    print(f"  {OUT_WEAPONS}")
    print(f"  {OUT_UPGRADES}")
    print(f"  {OUT_REPORT}")
    print()
    print("Counts:")
    print(json.dumps(report(weapons_out, upgrades_out), indent=2))


if __name__ == "__main__":
    main()
