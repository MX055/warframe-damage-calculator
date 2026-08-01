from collections.abc import Iterable

from ..domain.damage import Dist
from ..domain.status import COMBINED_STATUS_COMPONENTS, RANDOM_STATUS_TYPES, STATUS_TYPES, StatusModel, _product, attack_proc_chance
from ..domain.upgrades import ResolvedEffect
from ..domain.weapons import Attack
from .automatic import automatic_value
from .formulas import clamp
from .models.stats import ResolvedStats


AFFLICTIONS_CATEGORIES = frozenset({"lifted", "knockdown", "ragdoll"})
PROC_STATS = frozenset(f"{damage_type}_proc" for damage_type in STATUS_TYPES)


def _status_vulnerability(effects: Iterable[ResolvedEffect]) -> float:
    return max(1 + sum(float(effect.value) for effect in effects if effect.stat == "status_vulnerability"), 0)


def _derived_chances(crit: float, status: float, total: ResolvedStats) -> tuple[float, float]:
    crit_conversion = sum(float(bucket.get("crit_from_status", 0)) for bucket in (total.proportional, total.base, total.flat))
    status_conversion = sum(float(bucket.get("status_from_crit", 0)) for bucket in (total.proportional, total.base, total.flat))
    if crit_conversion:
        value = status * crit_conversion
        crit += min(value, total.maximums.get("crit_from_status", value))
    if status_conversion:
        value = crit * status_conversion
        status += min(value, total.maximums.get("status_from_crit", value))
    return max(crit, 0), max(status, 0)


def _forced_procs(attack: Attack, effects: Iterable[ResolvedEffect]) -> Dist:
    forced = attack.stats.forced_procs
    for effect in effects:
        if effect.stat not in PROC_STATS or automatic_value(effect, "on") is not None: continue
        forced += Dist({effect.stat.removesuffix("_proc"): float(effect.value)})
    return forced


def _status_model(damage: Dist, forced_procs: Dist, status_chance: float, attempts: float, attack_rate: float, duration: float, effects: Iterable[ResolvedEffect], crit_chance: float, *, include_random: bool = True, afflictions: bool = False) -> StatusModel:
    effects = tuple(effects)
    base = StatusModel(damage, forced_procs, status_chance, attempts, attack_rate, duration)
    direct_counts: dict[str, float] = {}
    direct_probabilities: dict[str, float] = {}
    critical_counts: dict[str, float] = {}
    for effect in effects:
        if effect.stat not in PROC_STATS or automatic_value(effect, "on") != "critical_hit": continue
        kind = effect.stat.removesuffix("_proc")
        chance = clamp(float(effect.value) * min(max(crit_chance, 0), 1), 0, 1)
        direct_counts[kind] = direct_counts.get(kind, 0) + chance
        direct_probabilities[kind] = 1 - (1 - direct_probabilities.get(kind, 0)) * (1 - chance)
        critical_counts[kind] = critical_counts.get(kind, 0) + chance * max(attempts, 0)
    direct_any_per_attempt = 1 - _product(1 - probability for probability in direct_probabilities.values())
    triggered_counts: dict[str, float] = {}
    triggered_probabilities: dict[str, float] = {}
    for effect in effects:
        event = "impact_status_proc" if effect.stat == "bleed_on_impact" else automatic_value(effect, "on")
        if effect.stat not in PROC_STATS and effect.stat != "bleed_on_impact": continue
        if event == "any_status_proc":
            source_probability = 1 - (1 - base.base_any_proc_probability_per_attempt()) * (1 - direct_any_per_attempt)
        elif isinstance(event, str) and event.endswith("_status_proc"):
            source = event.removesuffix("_status_proc")
            source_probability = base.base_proc_probability_per_attempt(source)
            source_probability = 1 - (1 - source_probability) * (1 - direct_probabilities.get(source, 0))
        else:
            continue
        kind = "slash" if effect.stat == "bleed_on_impact" else effect.stat.removesuffix("_proc")
        chance = clamp(float(effect.value) * source_probability, 0, 1)
        triggered_counts[kind] = triggered_counts.get(kind, 0) + chance
        triggered_probabilities[kind] = 1 - (1 - triggered_probabilities.get(kind, 0)) * (1 - chance)
    extra_per_attempt = {kind: direct_counts.get(kind, 0) + triggered_counts.get(kind, 0) for kind in set(direct_counts) | set(triggered_counts)}
    extra_probabilities_per_attempt = {kind: 1 - (1 - direct_probabilities.get(kind, 0)) * (1 - triggered_probabilities.get(kind, 0)) for kind in set(direct_probabilities) | set(triggered_probabilities)}
    extra_counts = Dist({kind: count * max(attempts, 0) for kind, count in extra_per_attempt.items()})
    extra_probabilities = Dist({kind: attack_proc_chance(probability, max(attempts, 0)) for kind, probability in extra_probabilities_per_attempt.items()})
    extra_any_per_attempt = 1 - _product(1 - probability for probability in extra_probabilities_per_attempt.values())
    extra_any_probability = attack_proc_chance(extra_any_per_attempt, max(attempts, 0))
    any_per_attempt = 1 - (1 - base.base_any_proc_probability_per_attempt()) * (1 - extra_any_per_attempt)
    random_chance = clamp(sum(float(effect.value) for effect in effects if include_random and effect.stat == "random_proc" and automatic_value(effect, "on") == "any_status_proc"), 0, 1)
    random_probability = attack_proc_chance(random_chance * any_per_attempt, max(attempts, 0))
    random_triggered: dict[str, float] = {}
    if random_probability > 0:
        for effect in effects:
            if effect.stat not in PROC_STATS: continue
            event = automatic_value(effect, "on")
            if not isinstance(event, str) or not event.endswith("_status_proc"): continue
            source = event.removesuffix("_status_proc")
            if source not in RANDOM_STATUS_TYPES: continue
            kind = effect.stat.removesuffix("_proc")
            chance = random_probability / len(RANDOM_STATUS_TYPES) * clamp(float(effect.value), 0, 1)
            chance *= 1 - extra_probabilities.get(kind, 0)
            random_triggered[kind] = random_triggered.get(kind, 0) + chance
    random_triggered_procs = Dist(random_triggered)
    extra_counts += random_triggered_procs
    extra_probabilities += random_triggered_procs
    provisional = StatusModel(damage, forced_procs, status_chance, attempts, attack_rate, duration, extra_counts, extra_probabilities, extra_any_probability, random_probability, random_triggered_procs, Dist(critical_counts))
    debilitate = clamp(sum(float(effect.value) for effect in effects if effect.stat == "debilitate_proc_chance"), 0, 1)
    if debilitate:
        additions: dict[str, float] = {}
        for combined, components in COMBINED_STATUS_COMPONENTS.items():
            activation = min(provisional.expected_stacks(combined, 10) / 10, 1)
            produced = provisional.proc_count_per_attack(combined) * debilitate * activation / len(components)
            for component in components: additions[component] = additions.get(component, 0) + produced
        extra_counts += Dist(additions)
        extra_probabilities += Dist({kind: min(value, 1) for kind, value in additions.items()})
    if afflictions:
        multiplier = sum(float(effect.value) for effect in effects if effect.stat == "afflictions_proc_multiplier")
        existing = StatusModel(damage, forced_procs, status_chance, attempts, attack_rate, duration, extra_counts, extra_probabilities, extra_any_probability, random_probability, random_triggered_procs, Dist(critical_counts))
        copied = Dist({kind: existing.proc_count_per_attack(kind) * multiplier for kind in RANDOM_STATUS_TYPES | {"void"}})
        extra_counts += copied
        critical_counts = {kind: value * (1 + multiplier) for kind, value in critical_counts.items()}
    return StatusModel(damage, forced_procs, status_chance, attempts, attack_rate, duration, extra_counts, extra_probabilities, extra_any_probability, random_probability, random_triggered_procs, Dist(critical_counts))


def _with_random_proc(model: StatusModel, effects: Iterable[ResolvedEffect], probability: float) -> StatusModel:
    triggered: dict[str, float] = {}
    for effect in effects:
        if effect.stat not in PROC_STATS: continue
        event = automatic_value(effect, "on")
        if not isinstance(event, str) or not event.endswith("_status_proc"): continue
        source = event.removesuffix("_status_proc")
        if source not in RANDOM_STATUS_TYPES: continue
        kind = effect.stat.removesuffix("_proc")
        triggered[kind] = triggered.get(kind, 0) + probability / len(RANDOM_STATUS_TYPES) * clamp(float(effect.value), 0, 1)
    random_triggered = Dist(triggered)
    return StatusModel(model.damage, model.forced_procs, model.status_chance, model.attempts_per_attack, model.attack_rate, model.duration, model.extra_proc_counts + random_triggered, model.extra_proc_probabilities + random_triggered, model.extra_any_proc_probability, probability, random_triggered, model.critical_proc_counts)


def _special_value(effects: Iterable[ResolvedEffect], stat: str, event: str | None = None) -> float:
    return sum(float(effect.value) for effect in effects if effect.stat == stat and (event is None or automatic_value(effect, "on") == event))
