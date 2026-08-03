from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from ..domain.attacks import Attack, AttackStats, Falloff, Inheritance, Links, RelatedAttacks, match_related_keys
from ..domain.damage import Dist
from ..domain.status import StatusModel, _product
from ..domain.effects import Source, resolve_source
from ..domain.upgrades import ResolvedEffect
from ..domain.generated_attacks import GENERATED_ATTACK_STAT
from .attack_calculator import AttackCalculator, derive_event_attack, derive_status_attack
from .automatic import automatic_value, automatic_values
from .context import CalculationContext
from .models.attack import ResolvedAttack, ResolvedAttackMetrics, PreliminaryAttack
from .status import AFFLICTIONS_CATEGORIES, _special_value, _status_model, _with_random_proc


def _attack_definition(attack: Attack) -> dict[str, object]:
    if isinstance(attack.stats, AttackStats):
        stats: dict[str, object] = {}
        for field_name in attack.stats.__dataclass_fields__:
            value = getattr(attack.stats, field_name)
            if isinstance(value, Dist):
                stats[field_name] = dict(value)
            elif isinstance(value, Falloff):
                if value: stats[field_name] = value.to_record()
            elif isinstance(value, Mapping):
                stats[field_name] = deepcopy(dict(value))
            else:
                stats[field_name] = deepcopy(value)
    else:
        stats = deepcopy(dict(attack.stats))
    links: dict[str, object] = {}
    if attack.links.children is not None: links["children"] = attack.links.children.to_record()
    if attack.links.parents is not None: links["parents"] = attack.links.parents.to_record()
    return {
        "trigger": deepcopy(attack.trigger),
        "delivery": deepcopy(attack.delivery),
        "form": deepcopy(attack.form),
        "category": deepcopy(attack.category),
        "aoe": deepcopy(attack.aoe),
        "links": links,
        "stats": stats,
    }


def _merge_attack_mappings(inherited: Mapping[str, object], explicit: Mapping[str, object]) -> dict[str, object]:
    merged = deepcopy(dict(inherited))
    for key, value in explicit.items():
        current = merged.get(key)
        merged[key] = _merge_attack_mappings(current, value) if isinstance(current, Mapping) and isinstance(value, Mapping) else deepcopy(value)
    return merged


def _inherit_field(source: Mapping[str, object], target: dict[str, object], path: str) -> bool:
    parts = path.split(".")
    value: object = source
    for part in parts:
        if not isinstance(value, Mapping) or part not in value:
            if parts[0] == "stats" and len(parts) == 3 and parts[1] in {"damage", "forced_procs"}: return False
            raise ValueError(f"attack inheritance field {path!r} does not exist on the parent")
        value = value[part]
    destination = target
    for part in parts[:-1]:
        existing = destination.get(part)
        if existing is None:
            nested: dict[str, object] = {}
            destination[part] = nested
            destination = nested
        elif isinstance(existing, dict):
            destination = existing
        else:
            raise ValueError(f"attack inheritance field {path!r} conflicts with another inherited field")
    destination[parts[-1]] = deepcopy(value)
    return True


def _delete_field(target: dict[str, object], path: str) -> None:
    parts = path.split(".")
    destination: object = target
    for part in parts[:-1]:
        if not isinstance(destination, dict) or part not in destination: return
        destination = destination[part]
    if isinstance(destination, dict): destination.pop(parts[-1], None)


def resolve_attack_inheritance(definition: Mapping[str, object], parent: Attack) -> dict[str, object]:
    inheritance_record = definition.get("inheritance")
    inherited: dict[str, object] = {}
    if inheritance_record is not None:
        inheritance = inheritance_record if isinstance(inheritance_record, Inheritance) else Inheritance.from_record(inheritance_record)
        if inheritance is not None:
            parent_definition = _attack_definition(parent)
            for path in inheritance.include: _inherit_field(parent_definition, inherited, path)
            for path in inheritance.exclude: _delete_field(inherited, path)
    explicit = {key: value for key, value in definition.items() if key not in {"inheritance", "automatic"}}
    return _merge_attack_mappings(inherited, explicit)


def _resolve_attack_expressions(value: object, parent: Attack) -> object:
    if isinstance(value, Source): return resolve_source(value, {"parent": parent})
    if isinstance(value, Mapping):
        if "source" in value: return resolve_source(Source.from_record(value), {"parent": parent})
        return {key: _resolve_attack_expressions(item, parent) for key, item in value.items()}
    if isinstance(value, list): return [_resolve_attack_expressions(item, parent) for item in value]
    return deepcopy(value)


class WeaponCalculator:
    __slots__ = ("context", "upgrade_effects", "evolution_effects", "attack_effects", "definitions", "origins", "attacks", "root_name", "prepared_names", "prepared_upgrade_effects")

    def __init__(self, context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> None:
        self.context = context
        self.upgrade_effects: tuple[ResolvedEffect, ...] = ()
        self.evolution_effects: tuple[ResolvedEffect, ...] = ()
        self.attack_effects: tuple[ResolvedEffect, ...] = ()
        self.definitions = dict(context.weapon.attacks)
        self.origins: dict[str, tuple[str, str]] = {}
        self.attacks: AttackCalculator
        self.root_name = context.attack
        self.prepared_names = prepared_names
        self.prepared_upgrade_effects = prepared_upgrade_effects

    def prepare_effects(self) -> None:
        resolved = self.prepared_upgrade_effects if self.prepared_upgrade_effects is not None else tuple(effect for upgrade in self.context.build.ranked_upgrades if upgrade.implemented for effect in upgrade.resolve_manual())
        self.attack_effects = tuple(effect for effect in resolved if effect.stat == GENERATED_ATTACK_STAT)
        self.upgrade_effects = tuple(effect for effect in resolved if effect.stat != GENERATED_ATTACK_STAT)
        self.evolution_effects = tuple(effect for perk in self.context.resolved_perks for effect in perk.effects)
        self.origins = {}
        self.attacks = AttackCalculator(self.context, self.upgrade_effects, self.evolution_effects)

    @staticmethod
    def _attack_template(effect: ResolvedEffect) -> Mapping[str, object]:
        if not isinstance(effect.value, Mapping): raise TypeError("generated_attack value must be an object")
        return effect.value

    @staticmethod
    def _parents(effect: ResolvedEffect) -> RelatedAttacks | None:
        template = WeaponCalculator._attack_template(effect)
        links = template.get("links")
        if links is None: return None
        parsed = links if isinstance(links, Links) else Links.from_record(links)
        return parsed.parents

    @staticmethod
    def _matches_parent(name: str, attack: Attack, selector: RelatedAttacks) -> bool:
        return selector.matches(name, attack)

    @classmethod
    def _parent_name(cls, effect: ResolvedEffect, definitions: Mapping[str, Attack], preferred: str | None = None, *, generated_keys: frozenset[str] = frozenset()) -> str | None:
        selector = cls._parents(effect)
        if selector is None: return None
        matches: list[str] = []
        explicit_names = {item.casefold() for item in (selector.names or ())}
        for name, attack in definitions.items():
            if name in generated_keys and name.casefold() not in explicit_names and attack.name.casefold() not in explicit_names: continue
            if cls._matches_parent(name, attack, selector) and name not in matches: matches.append(name)
        if not matches: return None
        if preferred in matches: return preferred
        if len(matches) > 1: raise ValueError(f"extra attack {effect.source!r} matches multiple parents: {', '.join(matches)}")
        return matches[0]

    @classmethod
    def _generated_attack(cls, effect: ResolvedEffect, parent: Attack, parent_name: str) -> Attack:
        template = dict(cls._attack_template(effect))
        resolved = _resolve_attack_expressions(resolve_attack_inheritance(template, parent), parent)
        if not isinstance(resolved, Mapping): raise TypeError("resolved extra attack must be an object")
        values = dict(resolved)
        name = values.get("name")
        if not isinstance(name, str) or not name: raise ValueError("generated_attack.name is required")
        stats = values.get("stats", {})
        if not isinstance(stats, Mapping): raise TypeError("generated_attack.stats must be an object")
        values["stats"] = AttackStats.from_record(stats)
        values["links"] = Links.from_record(values.get("links"))
        values.pop("inheritance", None)
        values.pop("automatic", None)
        return Attack(**{key: value for key, value in values.items() if key in Attack.__dataclass_fields__})

    @classmethod
    def _generated_key(cls, effect: ResolvedEffect) -> str:
        name = cls._attack_template(effect).get("name")
        if not isinstance(name, str) or not name: raise ValueError("generated_attack.name is required")
        return name.replace(" ", "_").casefold()

    @classmethod
    def _generated_status_types(cls, effect: ResolvedEffect) -> set[str]:
        on_events = [str(event) for event in automatic_values(effect, "on")]
        typed = {event.removesuffix("_status_proc") for event in on_events if event.endswith("_status_proc") and event != "status_proc"}
        if typed: return typed
        stats = cls._attack_template(effect).get("stats", {})
        damage = stats.get("damage", {}) if isinstance(stats, Mapping) else {}
        return set(damage) if isinstance(damage, Mapping) else set()

    @staticmethod
    def _status_trigger_events(effect: ResolvedEffect) -> tuple[str, ...]:
        on_events = [str(event) for event in automatic_values(effect, "on")]
        if not on_events: return ()
        if on_events == ["status_proc"]: return ("status_proc",)
        if all(event.endswith("_status_proc") for event in on_events): return tuple(on_events)
        return ()

    @staticmethod
    def _strip_stale_generated_children(attack: Attack, stale_keys: set[str]) -> None:
        children = attack.links.children
        if children is None or children.names is None: return
        remaining = [name for name in children.names if name.casefold() not in stale_keys and name.replace(" ", "_").casefold() not in stale_keys]
        if len(remaining) == len(children.names): return
        if remaining:
            attack.links.children = RelatedAttacks(names=remaining, triggers=children.triggers, deliveries=children.deliveries, forms=children.forms, categories=children.categories, aoe=children.aoe)
            return
        if any(value is not None for value in (children.triggers, children.deliveries, children.forms, children.categories, children.aoe)):
            attack.links.children = RelatedAttacks(triggers=children.triggers, deliveries=children.deliveries, forms=children.forms, categories=children.categories, aoe=children.aoe)
        else:
            attack.links.children = None

    def _base_definitions(self) -> dict[str, Attack]:
        # Result weapons retain previously derived generated attacks. Strip keys that
        # current upgrades will rebuild, and also strip leftover generated attacks whose
        # source upgrade is no longer equipped so leave-one-out contributions cannot keep
        # scoring a stale full-damage copy.
        rebuild_keys = {self._generated_key(effect) for effect in self.attack_effects}
        stale_keys = set(rebuild_keys)
        stale_keys.update(key for key in self.context.weapon.attacks if key not in self.context.weapon.intrinsic_attacks and key not in rebuild_keys)
        stale_folded = {key.casefold() for key in stale_keys}
        definitions: dict[str, Attack] = {}
        for key, attack in self.context.weapon.attacks.items():
            if key in stale_keys: continue
            clone = attack.copy()
            self._strip_stale_generated_children(clone, stale_folded)
            definitions[key] = clone
        return definitions

    def collect_attack_tree(self) -> list[str]:
        ordered: list[str] = []
        equipped = {upgrade.name for upgrade in self.context.build.ranked_upgrades}
        self.definitions = self._base_definitions()
        self.origins = {}

        for effect in self.attack_effects:
            if effect.automatic: continue
            parent_name = self._parent_name(effect, self.definitions, self.root_name, generated_keys=frozenset(self.origins))
            if parent_name is None: continue
            if parent_name not in self.definitions: raise ValueError(f"unknown generated attack parent {parent_name!r}")
            name = self._generated_key(effect)
            if name in self.definitions: raise ValueError(f"duplicate generated attack {name!r}")
            parent = self.definitions[parent_name].copy()
            generated = self._generated_attack(effect, parent, parent_name)
            parent.links.add_child_key(name)
            self.definitions[parent_name] = parent
            self.definitions[name] = generated
            self.origins[name] = (effect.source, parent_name)

        def collect(name: str, path: frozenset[str] = frozenset()) -> None:
            if name in path: raise ValueError(f"attack relationship cycle at {name!r}")
            if name not in self.definitions: raise ValueError(f"unknown child attack {name!r}")
            origin = self.origins.get(name)
            if origin is not None and origin[0] not in equipped:
                if name == self.root_name: raise ValueError(f"attack {name!r} requires {origin[0]}")
                return
            if name in ordered: return
            ordered.append(name)
            children = self.definitions[name].links.children
            if children is not None:
                for child in match_related_keys(children, self.definitions):
                    if child == name: continue
                    collect(child, path | {name})

        collect(self.root_name)
        return ordered

    def calculate_preliminary_attacks(self, names: list[str]) -> dict[str, PreliminaryAttack]:
        return {name: self.attacks.calculate_preliminary(self.definitions[name]) for name in names}

    def build_shared_status_model(self, preliminary: dict[str, PreliminaryAttack], names: list[str]) -> tuple[StatusModel, dict[str, float], float, float]:
        event_factors: dict[str, float] = {}
        for effect in self.attack_effects:
            if self._status_trigger_events(effect): continue
            event = automatic_value(effect, "on")
            if event is None: continue
            parent_name = self._parent_name(effect, {name: self.definitions[name] for name in names}, self.root_name, generated_keys=frozenset(self.origins))
            if parent_name is None: continue
            parent = preliminary[parent_name]
            probability = self._event_expectation(effect, parent.trigger_crit_chance)
            if probability > 0: event_factors[parent_name] = event_factors.get(parent_name, 0) + probability
        preliminary_models = [preliminary[name].status_model.with_attempt_multiplier(1 + event_factors.get(name, 0)) for name in names]
        root_rate = preliminary[self.root_name].attack_rate
        root_duration = max((model.duration for model in preliminary_models), default=0)
        random_probabilities: list[float] = []
        for name in names:
            result = preliminary[name]
            effects = result.special_effects
            model = _status_model(result.damage, result.forced_procs, result.status_chance, result.multishot, result.attack_rate, result.status_duration, effects, result.crit_chance, afflictions=bool(AFFLICTIONS_CATEGORIES & set(result.forced_procs)))
            random_probabilities.append(model.random_proc_probability)
        random_probability = 1 - _product(1 - probability for probability in random_probabilities)
        shared = StatusModel.combine(preliminary_models, root_rate, root_duration)
        shared = _with_random_proc(shared, preliminary[self.root_name].special_effects, random_probability)
        return shared, shared.non_damage_effects(), random_probability, root_duration

    def calculate_final_attacks(self, names: list[str], preliminary: dict[str, PreliminaryAttack], shared: StatusModel, status_effects: dict[str, float], random_probability: float, *, compact: bool = False) -> dict[str, ResolvedAttack]:
        results: dict[str, ResolvedAttack] = {}
        for name in names:
            origin = self.origins.get(name)
            result = self.attacks.calculate(
                self.definitions[name],
                automatic_model=shared,
                status_effects=status_effects,
                random_proc_probability=random_probability if name == self.root_name else 0,
                compact=compact,
                provisional=preliminary[name].provisional,
                generated_by=None if origin is None else origin[0],
            )
            if origin is not None:
                result.generated_by, result.generated_from = origin
            results[name] = result
        return results

    def derive_status_attacks(self, results: dict[str, ResolvedAttack], names: list[str]) -> None:
        for effect in self.attack_effects:
            trigger_events = self._status_trigger_events(effect)
            if not trigger_events: continue
            parent_name = self._parent_name(effect, {name: result.attack for name, result in results.items()}, self.root_name, generated_keys=frozenset(self.origins))
            if parent_name is None: continue
            if parent_name not in results: continue
            parent = results[parent_name]
            conditions = [str(condition) for condition in automatic_values(effect, "when") if str(condition).endswith("_status_proc")]
            if any(parent.effective.status_model.proc_count_per_attack(condition.removesuffix("_status_proc")) <= 0 for condition in conditions): continue
            chance = automatic_value(effect, "chance", 1)
            if not isinstance(chance, (int, float)) or isinstance(chance, bool): raise TypeError("generated_attack chance must be numeric")
            if float(chance) <= 0: continue
            name = self._generated_key(effect)
            if name in results: raise ValueError(f"duplicate generated attack {name!r}")
            attack = self._generated_attack(effect, parent.attack, parent_name)
            parent.attack = deepcopy(parent.attack)
            parent.attack.links.add_child_key(name)
            self.definitions[parent_name] = parent.attack
            self.definitions[name] = attack
            self.origins[name] = (effect.source, parent_name)
            status_types = self._generated_status_types(effect)
            derived = derive_status_attack(self.context, parent, attack, status_types)
            derived.generated_by, derived.generated_from = self.origins[name]
            if float(chance) != 1:
                derived.average.flat_dph = float(derived.average.flat_dph or 0) * float(chance)
                derived.average.flat_dotph = float(derived.average.flat_dotph or 0) * float(chance)
                derived.average.damage = derived.average.damage * float(chance)
                derived.effective.damage = derived.effective.damage * float(chance)
                from .formulas import refresh_metrics
                from .spatial import refresh_spatial
                refresh_metrics(derived.average)
                refresh_spatial(derived.spatial, derived.average.attack_rate)
            results[name] = derived
            names.append(name)

    def derive_event_attacks(self, results: dict[str, ResolvedAttack], names: list[str]) -> None:
        for effect in self.attack_effects:
            if self._status_trigger_events(effect): continue
            event = automatic_value(effect, "on")
            if event is None: continue
            parent_name = self._parent_name(effect, {name: result.attack for name, result in results.items()}, self.root_name, generated_keys=frozenset(self.origins))
            if parent_name is None: continue
            parent = results[parent_name]
            probability = self._event_expectation(effect, float(parent.effective.trigger_crit_chance))
            if probability <= 0: continue
            name = self._generated_key(effect)
            if name in results: raise ValueError(f"duplicate generated attack {name!r}")
            attack = self._generated_attack(effect, parent.attack, parent_name)
            parent.attack = deepcopy(parent.attack)
            parent.attack.links.add_child_key(name)
            self.definitions[parent_name] = parent.attack
            self.definitions[name] = attack
            self.origins[name] = (effect.source, parent_name)
            derived = derive_event_attack(parent, attack, probability)
            derived.generated_by, derived.generated_from = self.origins[name]
            results[name] = derived
            names.append(name)

    @classmethod
    def _effect_self_triggers(cls, effect: ResolvedEffect) -> bool:
        template = cls._attack_template(effect)
        links = template.get("links")
        if not isinstance(links, Mapping): return False
        children = links.get("children")
        if children is None: return False
        selector = children if isinstance(children, RelatedAttacks) else RelatedAttacks.from_record(children)
        name = template.get("name")
        if not isinstance(name, str) or not name: return False
        key = name.replace(" ", "_").casefold()
        stub = Attack(name=name)
        return key in match_related_keys(selector, {key: stub})

    @staticmethod
    def _event_probability(effect: ResolvedEffect, crit_chance: float) -> float:
        event = automatic_value(effect, "on")
        if event == "hit": probability = 1.0
        elif event == "near_yellow_critical_hit": probability = max(1 - abs(crit_chance - 1), 0)
        elif event == "critical_hit": probability = min(max(crit_chance, 0), 1)
        elif event == "non_critical_hit": probability = max(1 - crit_chance, 0)
        else: raise ValueError(f"unsupported generated_attack event {event!r}")
        chance = automatic_value(effect, "chance", 1)
        if not isinstance(chance, (int, float)) or isinstance(chance, bool): raise TypeError("generated_attack chance must be numeric")
        return min(max(probability * float(chance), 0), 1)

    @classmethod
    def _event_expectation(cls, effect: ResolvedEffect, crit_chance: float) -> float:
        probability = cls._event_probability(effect, crit_chance)
        if probability <= 0 or not cls._effect_self_triggers(effect): return probability
        if probability >= 1: raise ValueError(f"recursive generated attack {effect.source!r} requires chance < 1")
        # Geometric series: p + p^2 + p^3 + ... = p / (1 - p)
        return probability / (1 - probability)

    @staticmethod
    def _fold_metrics(output: ResolvedAttackMetrics, own: ResolvedAttackMetrics, children: list[ResolvedAttackMetrics]) -> None:
        direct_values = [own.flat_dph, *(child.flat_dph for child in children)]
        dot_values = [own.flat_dotph, *(child.flat_dotph for child in children)]
        if not any(value is not None for value in (*direct_values, *dot_values)):
            output.flat_dph = output.flat_dotph = output.total_dph = output.flat_dps = output.flat_dotps = output.total_dps = None
            return
        direct = sum(float(value or 0) for value in direct_values)
        dot = sum(float(value or 0) for value in dot_values)
        output.flat_dph = direct
        output.flat_dotph = dot
        output.total_dph = direct + dot
        output.flat_dps = direct * own.attack_rate
        output.flat_dotps = dot * own.attack_rate
        output.total_dps = (direct + dot) * own.attack_rate

    def aggregate_attack_tree(self, results: dict[str, ResolvedAttack], names: list[str], root_duration: float) -> tuple[ResolvedAttackMetrics, StatusModel, dict[str, float]]:
        root = results[self.root_name]
        status_names = [name for name in names if results[name].attack.hits_source]
        group_model = StatusModel.combine([results[name].effective.status_model for name in status_names], root.average.attack_rate, root_duration)
        status_effects = group_model.non_damage_effects()
        status_effects["armor_reduction"] = min(status_effects.get("puncture", 0) * _special_value(root.effective.special_effects, "armor_reduction"), 1)
        aggregate = ResolvedAttackMetrics(**{name: deepcopy(getattr(root.average, name)) for name in root.average.__dataclass_fields__})
        descendants: list[str] = []

        def collect(name: str, path: frozenset[str] = frozenset()) -> None:
            if name in path: raise ValueError(f"attack relationship cycle at {name!r}")
            children = results[name].attack.links.children
            if children is None: return
            for child in match_related_keys(children, {key: result.attack for key, result in results.items()}):
                if child == name: continue
                if child not in results: continue
                if child not in descendants: descendants.append(child)
                collect(child, path | {name})

        collect(self.root_name)
        self._fold_metrics(aggregate, root.average, [results[name].average for name in descendants if results[name].attack.hits_source])
        return aggregate, group_model, status_effects

    def calculate_metric_components(self) -> tuple[float, float, float, float, float]:
        self.prepare_effects()
        collected = self.collect_attack_tree()
        names = list(self.prepared_names) if self.prepared_names is not None else collected
        preliminary = self.calculate_preliminary_attacks(names)
        shared, status_effects, random_probability, _ = self.build_shared_status_model(preliminary, names)
        results = self.calculate_final_attacks(names, preliminary, shared, status_effects, random_probability, compact=True)
        self.derive_status_attacks(results, names)
        self.derive_event_attacks(results, names)
        root = results[self.root_name]
        source_names = [name for name in names if results[name].attack.hits_source]
        direct_dph = sum(float(results[name].average.flat_dph or 0) for name in source_names)
        dot_dph = sum(float(results[name].average.flat_dotph or 0) for name in source_names)
        attack_rate = float(root.average.attack_rate)
        total_dph = direct_dph + dot_dph
        weighted_damage_mass = sum((float(results[name].average.flat_dph or 0) + float(results[name].average.flat_dotph or 0)) * (float(results[name].spatial.damage_mass) if results[name].spatial.damage_mass is not None else 1.0) for name in names)
        damage_mass = weighted_damage_mass / total_dph if total_dph > 0 else 1.0
        return direct_dph, dot_dph, direct_dph * attack_rate, dot_dph * attack_rate, damage_mass

    def calculate(self) -> tuple[dict[str, ResolvedAttack], ResolvedAttackMetrics, StatusModel, dict[str, float]]:
        self.prepare_effects()
        collected = self.collect_attack_tree()
        names = list(self.prepared_names) if self.prepared_names is not None else collected
        preliminary = self.calculate_preliminary_attacks(names)
        shared, status_effects, random_probability, root_duration = self.build_shared_status_model(preliminary, names)
        results = self.calculate_final_attacks(names, preliminary, shared, status_effects, random_probability)
        self.derive_status_attacks(results, names)
        self.derive_event_attacks(results, names)
        aggregate, aggregate_status_model, aggregate_status_effects = self.aggregate_attack_tree(results, names, root_duration)
        return results, aggregate, aggregate_status_model, aggregate_status_effects


def calculate_weapon(context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> tuple[dict[str, ResolvedAttack], ResolvedAttackMetrics, StatusModel, dict[str, float]]:
    return WeaponCalculator(context, prepared_names, prepared_upgrade_effects).calculate()


def calculate_metric_components(context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> tuple[float, float, float, float, float]:
    return WeaponCalculator(context, prepared_names, prepared_upgrade_effects).calculate_metric_components()
