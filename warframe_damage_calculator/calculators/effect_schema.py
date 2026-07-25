"""Behaviour-based special-effect encoding.

JSON modes: ``proportional`` (default / omit), ``base``, ``flat``.
Family: product pool (``common`` default; ``bonus``, ``chamber``, ``charge``, ``status``, …).
Behaviour: closed special-case tag; numeric constants live here, not in JSON.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

COMMON_FAMILY = "common"
BONUS_FAMILY = "bonus"
STATUS_FAMILY = "status"

JSON_MODES = frozenset({"proportional", "base", "flat"})

BEHAVIOUR_FIRST_SHOT = "FIRST_SHOT"
BEHAVIOUR_LAST_SHOT = "LAST_SHOT"
BEHAVIOUR_DOUBLE_FOR_BOWS = "DOUBLE_FOR_BOWS"
BEHAVIOUR_ON_CRIT = "ON_CRIT"
BEHAVIOUR_ON_IMPACT_FR = "ON_IMPACT_DOUBLE_BELOW_2_5_FR"
BEHAVIOUR_ON_ANY_PROC = "ON_ANY_PROC"
BEHAVIOUR_ON_HIT = "ON_HIT"
BEHAVIOUR_STACK_RESET_CRIT_2_PLUS = "STACK_RESET_CRIT_2_PLUS"
BEHAVIOUR_NEAR_YELLOW = "NEAR_YELLOW"
BEHAVIOUR_FROM_PUNCTURE_X_STATUS = "FROM_PUNCTURE_X_STATUS"
BEHAVIOUR_UNIQUE_STATUS = "UNIQUE_STATUS"
BEHAVIOUR_STATUS_PROC_STACKS = "STATUS_PROC_STACKS"

ALLOWED_BEHAVIOURS = frozenset({
    BEHAVIOUR_FIRST_SHOT,
    BEHAVIOUR_LAST_SHOT,
    BEHAVIOUR_DOUBLE_FOR_BOWS,
    BEHAVIOUR_ON_CRIT,
    BEHAVIOUR_ON_IMPACT_FR,
    BEHAVIOUR_ON_ANY_PROC,
    BEHAVIOUR_ON_HIT,
    BEHAVIOUR_STACK_RESET_CRIT_2_PLUS,
    BEHAVIOUR_NEAR_YELLOW,
    BEHAVIOUR_FROM_PUNCTURE_X_STATUS,
    BEHAVIOUR_UNIQUE_STATUS,
    BEHAVIOUR_STATUS_PROC_STACKS,
})

ENERVATE_RESET_CHARGES_MAX = 6
DOUGHTY_PER = 0.1
IB_FIRE_RATE_THRESHOLD = 2.5


def normalize_mode(raw: Any) -> str:
    if raw is None or raw == "": return "proportional"
    mode = str(raw)
    if mode not in JSON_MODES: raise ValueError(f"unsupported effect mode {mode!r}; use proportional, base, or flat")
    return mode


def effect_family(effect: Mapping[str, Any]) -> str:
    family = effect.get("family")
    if family is None or not str(family).strip(): return COMMON_FAMILY
    return str(family)


def rank_scales(effect: Mapping[str, Any]) -> bool:
    if "rank_scale" in effect: return bool(effect["rank_scale"])
    return True


def behaviour_of(effect: Mapping[str, Any]) -> str | None:
    raw = effect.get("behaviour")
    if raw is None: return None
    name = str(raw)
    if name not in ALLOWED_BEHAVIOURS: raise ValueError(f"unsupported behaviour {name!r}")
    return name
