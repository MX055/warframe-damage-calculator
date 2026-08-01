from ..domain.damage import Dist
from ..domain.loadouts import Progenitor
from ..domain.weapons import Attack
from .aggregation import DAMAGE_TYPES
from .formulas import family_bonus
from .models.stats import ResolvedStats, Stats
from .stats import _combined
from .context import CalculationContext


DOT_MULTIPLIERS = {"slash": 0.35, "heat": 0.5, "toxin": 0.5, "electricity": 0.5, "gas": 0.5}
DEFERRED_FAMILIES = frozenset({"magazine_first_shot", "magazine_last_shot"})


def _base_damage(context: CalculationContext, attack: Attack, evolutions: ResolvedStats) -> tuple[Dist, Dist, Dist]:
    strength = float(context.state.ability_strength) if {"exalted", "pseudo_exalted"} & context.weapon.traits else 1.0
    displayed = attack.stats.damage * max(strength, 0)
    raw = Dist(displayed)
    conversion = sum(float(bucket.get("impact_to_puncture_conversion", 0)) for bucket in (evolutions.proportional, evolutions.base, evolutions.flat))
    if conversion > 0:
        for damage in (raw, displayed):
            if not damage.get("impact", 0): continue
            moved = damage.get("impact", 0) * min(conversion, 1)
            damage += Dist(impact=-moved, puncture=moved)
    original = Dist(raw)
    flat = float(evolutions.base.get("damage", 0))
    if flat:
        if raw.total: raw += Dist({kind: flat * raw.weight(kind) for kind in raw})
        if displayed.total: displayed += Dist({kind: flat * displayed.weight(kind) for kind in displayed})
    return raw, original, displayed


def _modified_damage(base: Dist, resolved: ResolvedStats, progenitor: Progenitor | None = None) -> Dist:
    recorded = resolved.proportional.get("damage", Dist())
    modifiers = {kind: float(value) for kind, value in recorded.items()} if isinstance(recorded, Dist) else {}
    modifiers.update({kind: float(value) for kind, value in resolved.proportional.items() if kind in DAMAGE_TYPES})
    if progenitor is not None:
        element = str(progenitor.element)
        bonus = modifiers.pop(element, 0) + float(progenitor.bonus)
        modifiers[element] = bonus
    return base.apply_modifiers(modifiers)


def _damage(attack: Attack, base: Dist, original: Dist, upgrades: ResolvedStats, evolutions: ResolvedStats, progenitor: Progenitor | None = None) -> Dist:
    total = _combined(upgrades, evolutions)
    evolved = _modified_damage(base, total, progenitor)
    original_modified = _modified_damage(original, total, progenitor)
    common = max(1 + attack.stats.damage_bonus + float(total.proportional.get("damage_bonus", 0)), 0)
    status_bonus = family_bonus(total, "unique_status", "damage_bonus")
    if attack.stats.co_effect == "multiplies":
        damage = evolved * common * max(1 + status_bonus, 1)
    else:
        damage = evolved * common + original_modified * max(status_bonus, 0)
    for family, stats in total.families.items():
        if family in {"unique_status", "non_critical_hit", "multishot_ammo", *DEFERRED_FAMILIES}: continue
        damage *= max(1 + float(stats.get("damage_bonus", 0)), 1)
    return damage


def _dot_base_damage(attack: Attack, base: Dist, original: Dist, upgrades: ResolvedStats, evolutions: ResolvedStats) -> float:
    total = _combined(upgrades, evolutions)
    common = max(1 + attack.stats.damage_bonus + float(total.proportional.get("damage_bonus", 0)), 0)
    status_bonus = family_bonus(total, "unique_status", "damage_bonus")
    value = base.total * common * max(1 + status_bonus, 1) if attack.stats.co_effect == "multiplies" else base.total * common + original.total * max(status_bonus, 0)
    for family, stats in total.families.items():
        if family in {"unique_status", "non_critical_hit", "multishot_ammo", *DEFERRED_FAMILIES}: continue
        value *= max(1 + float(stats.get("damage_bonus", 0)), 1)
    return value


def _elemental_dot_bonuses(total: ResolvedStats, progenitor: Progenitor | None = None) -> Stats:
    modifiers = total.proportional.get("damage", Dist())
    heat = float(modifiers.get("heat", 0)) if isinstance(modifiers, Dist) else 0
    electricity = float(modifiers.get("electricity", 0)) if isinstance(modifiers, Dist) else 0
    toxin = float(modifiers.get("toxin", 0)) if isinstance(modifiers, Dist) else 0
    if progenitor is not None:
        if progenitor.element == "heat": heat += float(progenitor.bonus)
        elif progenitor.element == "electricity": electricity += float(progenitor.bonus)
        elif progenitor.element == "toxin": toxin += float(progenitor.bonus)
    return Stats(heat=max(1 + heat, 0), electricity=max(1 + electricity, 0), toxin=max(1 + toxin, 0), gas=max(1 + heat + toxin, 0), slash=1.0)
