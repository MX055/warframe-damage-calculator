from typing import Literal, get_args


DamageType = Literal["impact", "puncture", "slash", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "cold", "electricity", "heat", "toxin", "void"]

DOT_MULTIPLIERS = (("slash", 2.1), ("heat", 3.0), ("toxin", 3.0), ("electricity", 3.0), ("gas", 3.0))
PHYSICAL_TYPES = ("impact", "puncture", "slash")
ELEMENTAL_TYPES = ("cold", "electricity", "heat", "toxin")
DAMAGE_TYPES = get_args(DamageType)
ELEMENTAL_COMBINATIONS = {frozenset(("cold", "heat")): "blast", frozenset(("electricity", "toxin")): "corrosive", frozenset(("heat", "toxin")): "gas", frozenset(("cold", "electricity")): "magnetic", frozenset(("electricity", "heat")): "radiation", frozenset(("cold", "toxin")): "viral"}
DAMAGE_TYPE_ORDER = {dt: idx for idx, dt in enumerate(get_args(DamageType))}

WEAPON_DIST_FIELDS = ("damage_dist", "forced_procs", "explosion_damage_dist", "explosion_forced_procs")
COMMON_WEAPON_PAYLOAD_FIELDS = {"name", "type", "damage_dist", "forced_procs", "crit_chance", "crit_damage", "status_chance"}
RANGED_WEAPON_PAYLOAD_FIELDS = COMMON_WEAPON_PAYLOAD_FIELDS | {"explosion_damage_dist", "explosion_forced_procs", "multishot", "fire_rate", "reload_speed", "magazine_capacity", "weakpoint_damage", "recharge_rate", "charge_time", "burst_count", "burst_delay", "is_beam", "is_battery"}
MELEE_WEAPON_PAYLOAD_FIELDS = COMMON_WEAPON_PAYLOAD_FIELDS | {"attack_speed"}
PRIMARY_TYPES = {"primary", "rifle", "bow", "shotgun", "sniper"}
SECONDARY_TYPES = {"secondary", "pistol"}
MELEE_TYPES = {"melee"}
TYPE_ALIASES = {"primary": {"primary", "rifle", "bow", "shotgun", "sniper"}, "primaries": {"primary", "rifle", "bow", "shotgun", "sniper"}, "secondary": {"pistol"}, "secondaries": {"pistol"}, "pistol": {"pistol"}, "melee": {"melee"}, "melees": {"melee"}}
