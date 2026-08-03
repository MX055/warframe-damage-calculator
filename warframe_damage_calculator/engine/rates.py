from collections.abc import Mapping
from typing import Any

from ..domain.upgrades import Combo, Upgrade
from ..domain.weapons import Attack
from .context import CalculationContext
from .formulas import clamp, family_bonus, family_factor, true_round
from .models.stats import ResolvedStats, Stats


HEAVY_CATEGORIES = frozenset({"heavy", "heavy_slam"})
SLAM_CATEGORIES = frozenset({"slam", "heavy_slam"})


def _stance(context: CalculationContext) -> Upgrade | None:
    return next((upgrade for upgrade in context.loadout.ranked_upgrades if upgrade.slot == "stance_mod"), None)


def _stance_combo(context: CalculationContext, attack: Attack) -> Combo | None:
    stance = _stance(context)
    if stance is None: return None
    if attack.category in HEAVY_CATEGORIES: key = "heavy"
    elif attack.category == "slide": key = "slide"
    elif attack.category == "slam": key = "slam"
    else: key = str(context.state.stance_combo)
    selected = next((combo for combo in stance.combos.values() if combo.type == key), None)
    if selected is not None: return selected
    return next((combo for combo in stance.combos.values() if combo.type == "neutral"), None)


def _multishot_ammo_bonus(total: ResolvedStats) -> float:
    return family_bonus(total, "multishot_ammo", "damage_bonus")


def _ranged_rate(context: CalculationContext, attack: Attack, total: ResolvedStats, multishot: float) -> tuple[float, float, Stats]:
    locked = bool(total.proportional.get("fire_rate_lock"))
    scale = 1.0 if locked else 1 + float(total.proportional.get("fire_rate", 0))
    fire_rate = max(float(attack.stats.fire_rate) * scale, 0.05)
    if not locked: fire_rate *= family_factor(total, "fire_rate")
    burst_count = max(float(attack.stats.burst_count), 1)
    burst_delay = max(float(attack.stats.burst_delay), 0) / max(scale, 1)
    charge_time = max(float(attack.stats.charge_time), 0) / max(scale, 0.01) / (family_factor(total, "fire_rate") if not locked else 1)
    incarnon = attack.form == "incarnon" and context.weapon.incarnon_charges is not None
    magazine_base = float(context.weapon.incarnon_charges) if incarnon else float(context.weapon.magazine_size)
    magazine = max(true_round(magazine_base if incarnon else (magazine_base + float(total.base.get("magazine_capacity", 0))) * (1 + float(total.proportional.get("magazine_capacity", 0))) + float(total.flat.get("magazine_capacity", 0))), 1)
    efficiency = 0.0 if incarnon else clamp(float(total.proportional.get("ammo_efficiency", 0)), 0, 1)
    ammo_cost = max(float(attack.stats.ammo_cost), 0)
    consumes_multishot = _multishot_ammo_bonus(total) != 0
    if consumes_multishot: ammo_cost *= max(multishot, 1)
    ammo_cost *= 1 - efficiency
    reload_time = float(context.weapon.reload_time) / max(1 + float(total.proportional.get("reload_speed", 0)), 0.01)
    if context.weapon.recharge_rate is not None and not incarnon:
        recharge_rate = max(float(context.weapon.recharge_rate), 0)
        reload_time += float("inf") if recharge_rate == 0 else magazine / recharge_rate
    if ammo_cost <= 0:
        sustained = fire_rate
    else:
        shots = magazine / ammo_cost
        bursts = shots / burst_count
        cycle = bursts * (charge_time + (burst_count - 1) * burst_delay)
        cycle += (bursts - 1) / fire_rate + reload_time
        sustained = float("inf") if cycle <= 0 else shots / cycle
    return fire_rate, sustained, Stats(ammo_cost=ammo_cost, ammo_efficiency=efficiency, magazine_capacity=magazine, reload_time=reload_time, burst_count=burst_count, burst_delay=burst_delay, charge_time=charge_time)


def _melee_rate(context: CalculationContext, attack: Attack, total: ResolvedStats, *, include_stance: bool = True) -> tuple[float, Stats]:
    heavy = attack.category in HEAVY_CATEGORIES
    speed_bonus = float(total.proportional.get("heavy_attack_speed" if heavy else "attack_speed", 0))
    base_speed = float(attack.stats.fire_rate if attack.stats.attack_speed is None else attack.stats.attack_speed)
    speed = max(base_speed * (1 + speed_bonus), 0)
    combo = _stance_combo(context, attack) if include_stance else None
    if combo is not None and combo.duration > 0 and combo.hits > 0:
        speed *= combo.hits / combo.duration
    return speed, Stats(attack_speed=speed, heavy_attack_speed=max(1 + float(total.proportional.get("heavy_attack_speed", 0)), 0), heavy_attack_efficiency=max(float(attack.stats.heavy_attack_efficiency) + float(total.proportional.get("heavy_attack_efficiency", 0)), 0), initial_combo=max(float(attack.stats.initial_combo) + float(total.proportional.get("initial_combo", 0)), 0), magazine_capacity=float(context.weapon.magazine_size), reload_time=float(context.weapon.reload_time), ammo_cost=float(attack.stats.ammo_cost), ammo_efficiency=0, burst_count=float(attack.stats.burst_count), burst_delay=float(attack.stats.burst_delay), charge_time=float(attack.stats.charge_time))
