from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any

from ..domain.results import Stats
from ..domain.upgrades import ResolvedEffect
from .status import StatusModel


def _tokens(effect: ResolvedEffect) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for token in effect.automatic: result[token.op].append(token.value)
    return result


def evaluate(effect: ResolvedEffect, *, weapon: Any, attack: Any, stats: Stats, status: StatusModel, equipped: set[str]) -> ResolvedEffect | None:
    tokens = _tokens(effect)
    equipped_names = {name.casefold() for name in equipped}
    if any(name.casefold() not in equipped_names for name in tokens.get("EQUIPPED", [])): return None
    scopes = {attack.form, attack.category, attack.delivery or "", "aoe" if attack.aoe else "normal"}
    if attack.delivery == "beam": scopes.add("continuous")
    if tokens.get("SCOPE") and not {value.lower() for value in tokens["SCOPE"]} & scopes: return None
    if {value.lower() for value in tokens.get("EXCLUDE", [])} & scopes: return None
    multiplier = 1.0
    source = tokens.get("WITH", [None])[0]
    maximum = tokens.get("STACKS", [None])[0]
    stack_limit = None if maximum in (None, "INF") else int(maximum)
    if source == "UNIQUE_STATUS_COUNT": multiplier *= status.expected_unique(stack_limit) * float(attack.stats.co_factor)
    elif source == "WEAPON_COMBO": multiplier *= min(float(weapon.runtime.combo), stack_limit) if stack_limit is not None else float(weapon.runtime.combo)
    elif source == "BOW_MULTIPLIER": multiplier *= 2 if weapon.subtype == "bow" else 1
    elif source == "EFFECTIVE_MULTISHOT" and effect.family != "multishot_ammo": multiplier *= float(stats.multishot)
    elif source == "PUNCTURE_STATUS_COUNT" and effect.stat != "crit_damage": multiplier *= status.expected_stacks("puncture", 5, status.duration)
    condition = tokens.get("WHEN", [None])[0]
    if condition and condition.endswith("_PROC"):
        maximum = tokens.get("STACKS", [None])[0]
        limit = None if maximum in (None, "INF") else int(maximum)
        duration = float(tokens.get("FOR", [status.duration])[0])
        multiplier *= status.expected_stacks(condition[:-5].lower(), limit, duration)
    elif condition == "CRIT_TIER_2_PLUS" and effect.stat != "crit_reset_charges": multiplier *= max(float(stats.crit_chance) - 1, 0)
    event = tokens.get("ON", [None])[0]
    if event == "CRIT" and effect.stat != "slash_proc": multiplier *= min(max(float(stats.crit_chance), 0), 1)
    elif event == "NEAR_YELLOW_CRIT" and effect.stat != "duplicated_hit": multiplier *= max(1 - abs(float(stats.crit_chance) - 1), 0)
    elif event == "NON_CRIT" and effect.family != "non_crit": multiplier *= max(1 - float(stats.crit_chance), 0)
    elif event == "ANY_PROC" and effect.stat != "random_proc": multiplier *= min(status.status_chance * status.attempts_per_attack, 1)
    elif event == "IMPACT_PROC" and effect.stat != "slash_proc": multiplier *= min(status.status_chance * status.attempts_per_attack * status.damage.weight("impact"), 1)
    if tokens.get("CHANCE") and effect.family != "non_crit": multiplier *= float(tokens["CHANCE"][0])
    if tokens.get("IF") == ["FIRE_RATE_BELOW_2.5"] and float(stats.fire_rate) < 2.5: multiplier *= float(tokens.get("MULTIPLY", [2])[0])
    if tokens.get("PER") and effect.stat not in {"crit_damage", "crit_reset_charges"}: multiplier *= float(tokens["PER"][0])
    value = effect.value * multiplier if isinstance(effect.value, (int, float)) and not isinstance(effect.value, bool) else effect.value
    mode = tokens.get("APPLY_MODE", [effect.mode])[0].lower()
    stat = effect.stat
    return replace(effect, stat=stat, value=value, mode=mode)
