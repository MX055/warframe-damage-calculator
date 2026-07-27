"""Behavior-based special-effect encoding.

JSON modes: ``proportional`` (default / omit), ``base``, ``flat``.
Family: product pool (``common`` default; ``bonus``, ``chamber``, ``charge``, ``status``, …).
Behavior: closed special-case tag; numeric constants live here, not in JSON.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

COMMON_FAMILY = "common"
BONUS_FAMILY = "bonus"
STATUS_FAMILY = "status"
NON_CRIT_FAMILY = "non_crit"
MULTISHOT_AMMO_FAMILY = "multishot_ammo"

JSON_MODES = frozenset({"proportional", "base", "flat"})

BEHAVIOR_FIRST_SHOT = "FIRST_SHOT"
BEHAVIOR_LAST_SHOT = "LAST_SHOT"
BEHAVIOR_DOUBLE_FOR_BOWS = "DOUBLE_FOR_BOWS"
BEHAVIOR_ON_CRIT = "ON_CRIT"
BEHAVIOR_ON_IMPACT_FR = "ON_IMPACT_DOUBLE_BELOW_2_5_FR"
BEHAVIOR_ON_ANY_PROC = "ON_ANY_PROC"
BEHAVIOR_ON_HIT = "ON_HIT"
BEHAVIOR_ON_NON_CRIT = "ON_NON_CRIT"
BEHAVIOR_MULTISHOT_CONSUMES_AMMO = "MULTISHOT_CONSUMES_AMMO"
BEHAVIOR_STACK_RESET_CRIT_2_PLUS = "STACK_RESET_CRIT_2_PLUS"
BEHAVIOR_NEAR_YELLOW = "NEAR_YELLOW"
BEHAVIOR_FROM_PUNCTURE_X_STATUS = "FROM_PUNCTURE_X_STATUS"
BEHAVIOR_UNIQUE_STATUS = "UNIQUE_STATUS"
BEHAVIOR_STATUS_EFFECT_STACKS = "STATUS_EFFECT_STACKS"
LEGACY_BEHAVIOR_ALIASES = {"STATUS_PROC_STACKS": BEHAVIOR_STATUS_EFFECT_STACKS}
BEHAVIOR_WEAPON_COMBO = "WEAPON_COMBO"

ALLOWED_BEHAVIORS = frozenset({
    BEHAVIOR_FIRST_SHOT,
    BEHAVIOR_LAST_SHOT,
    BEHAVIOR_DOUBLE_FOR_BOWS,
    BEHAVIOR_ON_CRIT,
    BEHAVIOR_ON_IMPACT_FR,
    BEHAVIOR_ON_ANY_PROC,
    BEHAVIOR_ON_HIT,
    BEHAVIOR_ON_NON_CRIT,
    BEHAVIOR_MULTISHOT_CONSUMES_AMMO,
    BEHAVIOR_STACK_RESET_CRIT_2_PLUS,
    BEHAVIOR_NEAR_YELLOW,
    BEHAVIOR_FROM_PUNCTURE_X_STATUS,
    BEHAVIOR_UNIQUE_STATUS,
    BEHAVIOR_STATUS_EFFECT_STACKS,
    BEHAVIOR_WEAPON_COMBO,
})

# Expected-value specials modeled by the calculator without a runtime toggle.
AUTOMATIC_BEHAVIORS = frozenset({
    BEHAVIOR_ON_CRIT,
    BEHAVIOR_ON_IMPACT_FR,
    BEHAVIOR_ON_ANY_PROC,
    BEHAVIOR_ON_HIT,
    BEHAVIOR_ON_NON_CRIT,
    BEHAVIOR_MULTISHOT_CONSUMES_AMMO,
    BEHAVIOR_STACK_RESET_CRIT_2_PLUS,
    BEHAVIOR_NEAR_YELLOW,
    BEHAVIOR_FROM_PUNCTURE_X_STATUS,
    BEHAVIOR_UNIQUE_STATUS,
    BEHAVIOR_STATUS_EFFECT_STACKS,
    BEHAVIOR_WEAPON_COMBO,
})

# Product families that must not fold into ordinary damage_bonus / crit product pools.
FOLD_EXCLUDED_FAMILIES = frozenset({NON_CRIT_FAMILY, MULTISHOT_AMMO_FAMILY})

ENERVATE_PER_STACK = 0.1  # flat crit chance per stack; reset charges come from DB value
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


def behavior_of(effect: Mapping[str, Any]) -> str | None:
    raw = effect.get("behavior")
    if raw is None: return None
    name = LEGACY_BEHAVIOR_ALIASES.get(str(raw), str(raw))
    if name not in ALLOWED_BEHAVIORS: raise ValueError(f"unsupported behavior {name!r}")
    return name


def is_automatic(effect: Mapping[str, Any], *, behavior: str | None = None) -> bool:
    """Whether this effect is modeled automatically (expected value, no runtime toggle)."""
    name = behavior if behavior is not None else behavior_of(effect)
    if name not in AUTOMATIC_BEHAVIORS: return False
    if "automatic" not in effect: raise ValueError(f"behavior {name!r} requires automatic: true")
    return bool(effect["automatic"])


def behavior_data_of(effect: Mapping[str, Any], *, behavior: str | None = None) -> dict[str, Any]:
    """Return behavior-specific payload; required whenever ``behavior`` is set."""
    name = behavior if behavior is not None else behavior_of(effect)
    if name is None: return {}
    raw = effect.get("behavior_data")
    if raw is None: raise ValueError(f"behavior {name!r} requires behavior_data")
    if not isinstance(raw, Mapping): raise ValueError(f"behavior_data must be an object for {name!r}")
    return dict(raw)
