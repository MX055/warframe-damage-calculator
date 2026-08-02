from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from ..domain.status import StatusModel, _product
from ..domain.effects import Source, resolve_source
from ..domain.upgrades import ResolvedEffect
from ..domain.weapons import Attack, AttackStats
from .attack_calculator import AttackCalculator, derive_event_attack, derive_status_attack
from .automatic import automatic_value, automatic_values
from .context import CalculationContext
from .models.attack import AttackResult, AverageAttackStats, PreliminaryAttack
from .status import AFFLICTIONS_CATEGORIES, _special_value, _status_model, _with_random_proc


class WeaponCalculator:
    __slots__ = ("context", "upgrade_effects", "evolution_effects", "attack_effects", "definitions", "attacks", "root_name", "prepared_names", "prepared_upgrade_effects")

    def __init__(self, context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> None:
        self.context = context
        self.upgrade_effects: tuple[ResolvedEffect, ...] = ()
        self.evolution_effects: tuple[ResolvedEffect, ...] = ()
        self.attack_effects: tuple[ResolvedEffect, ...] = ()
        self.definitions = dict(context.weapon.attacks)
        self.attacks: AttackCalculator
        self.root_name = context.attack
        self.prepared_names = prepared_names
        self.prepared_upgrade_effects = prepared_upgrade_effects

    def prepare_effects(self) -> None:
        resolved = self.prepared_upgrade_effects if self.prepared_upgrade_effects is not None else tuple(effect for upgrade in self.context.loadout.ranked_upgrades if upgrade.implemented for effect in upgrade.resolve_manual())
        self.attack_effects = tuple(effect for effect in resolved if effect.stat == "extra_attack")
        self.upgrade_effects = tuple(effect for effect in resolved if effect.stat != "extra_attack")
        self.evolution_effects = tuple(effect for perk in self.context.resolved_perks for effect in perk.effects)
        self.attacks = AttackCalculator(self.context, self.upgrade_effects, self.evolution_effects)

    @staticmethod
    def _attack_record(effect: ResolvedEffect) -> tuple[Mapping[str, object], Mapping[str, object]]:
        if not isinstance(effect.value, Mapping): raise TypeError("extra_attack value must be an object")
        parent = effect.value.get("parent")
        if not isinstance(parent, Mapping): raise TypeError("extra_attack.parent must be an attack selector")
        attack = effect.value.get("attack")
        if not isinstance(attack, Mapping): raise TypeError("extra_attack.attack must be an object")
        return parent, attack

    @staticmethod
    def _template_value(value: object, parent: Attack) -> object:
        if isinstance(value, Mapping) and "source" in value:
            return resolve_source(Source.from_record(value), {"parent": parent})
        return deepcopy(value)

    @staticmethod
    def _matches_parent(name: str, attack: Attack, selector: Mapping[str, object]) -> bool:
        fields = {"names": name, "triggers": attack.trigger, "deliveries": attack.delivery, "forms": attack.form, "categories": attack.category}
        for field, actual in fields.items():
            expected = selector.get(field)
            if expected is not None and actual not in expected: return False
        return selector.get("aoe") in (None, attack.aoe)

    @classmethod
    def _parent_name(cls, effect: ResolvedEffect, definitions: Mapping[str, Attack], preferred: str | None = None) -> str | None:
        selector, _ = cls._attack_record(effect)
        matches = [name for name, attack in definitions.items() if cls._matches_parent(name, attack, selector)]
        if not matches: return None
        if preferred in matches: return preferred
        if len(matches) > 1: raise ValueError(f"extra attack {effect.source!r} matches multiple parents: {', '.join(matches)}")
        return matches[0]

    @classmethod
    def _generated_attack(cls, effect: ResolvedEffect, parent: Attack) -> Attack:
        _, template = cls._attack_record(effect)
        name = template.get("name")
        if not isinstance(name, str) or not name: raise ValueError("extra_attack.attack.name is required")
        if template.get("inherit") != "$parent": raise ValueError("extra_attack.attack.inherit must be '$parent'")
        values: dict[str, object] = {field: deepcopy(getattr(parent, field)) for field in ("trigger", "delivery", "form", "category", "aoe", "children")}
        values.update(name=name, generated_by=effect.source)
        for field_name in ("trigger", "delivery", "form", "category", "aoe", "children"):
            if field_name in template: values[field_name] = cls._template_value(template[field_name], parent)
        stats_template = template.get("stats", {})
        if not isinstance(stats_template, Mapping): raise TypeError("extra_attack.attack.stats must be an object")
        stats = {field_name: deepcopy(getattr(parent.stats, field_name)) for field_name in parent.stats.__dataclass_fields__}
        for field_name, value in stats_template.items():
            if field_name in {"damage", "forced_procs", "falloff"}:
                if not isinstance(value, Mapping): raise TypeError(f"extra_attack.attack.stats.{field_name} must be an object")
                stats[field_name] = {key: cls._template_value(item, parent) for key, item in value.items()}
            else:
                if not hasattr(parent.stats, field_name): raise ValueError(f"unknown attack stat {field_name!r}")
                stats[field_name] = cls._template_value(value, parent)
        values["stats"] = AttackStats.from_record(stats)
        return Attack(**values)

    @classmethod
    def _generated_name(cls, effect: ResolvedEffect) -> str:
        _, attack = cls._attack_record(effect)
        name = attack.get("name")
        if not isinstance(name, str) or not name: raise ValueError("extra_attack.attack.name is required")
        return name

    @classmethod
    def _generated_status_types(cls, effect: ResolvedEffect) -> set[str]:
        _, attack = cls._attack_record(effect)
        stats = attack.get("stats", {})
        damage = stats.get("damage", {}) if isinstance(stats, Mapping) else {}
        return set(damage) if isinstance(damage, Mapping) else set()

    def collect_attack_tree(self) -> list[str]:
        ordered: list[str] = []
        equipped = {upgrade.name for upgrade in self.context.loadout.ranked_upgrades}
        self.definitions = dict(self.context.weapon.attacks)

        for effect in self.attack_effects:
            if effect.automatic: continue
            parent_name = self._parent_name(effect, self.definitions, self.root_name)
            if parent_name is None: continue
            if parent_name not in self.definitions: raise ValueError(f"unknown generated attack parent {parent_name!r}")
            name = self._generated_name(effect)
            if name in self.definitions: raise ValueError(f"duplicate generated attack {name!r}")
            parent = deepcopy(self.definitions[parent_name])
            generated = self._generated_attack(effect, parent)
            if name not in parent.children: parent.children.append(name)
            self.definitions[parent_name] = parent
            self.definitions[name] = generated

        def collect(name: str, path: frozenset[str] = frozenset()) -> None:
            if name in path: raise ValueError(f"attack relationship cycle at {name!r}")
            if name not in self.definitions: raise ValueError(f"unknown child attack {name!r}")
            generated_by = self.definitions[name].generated_by
            if generated_by is not None and generated_by not in equipped:
                if name == self.root_name: raise ValueError(f"attack {name!r} requires {generated_by}")
                return
            if name in ordered: return
            ordered.append(name)
            for child in self.definitions[name].children: collect(child, path | {name})

        collect(self.root_name)
        return ordered

    def calculate_preliminary_attacks(self, names: list[str]) -> dict[str, PreliminaryAttack]:
        return {name: self.attacks.calculate_preliminary(self.definitions[name]) for name in names}

    def build_shared_status_model(self, preliminary: dict[str, PreliminaryAttack], names: list[str]) -> tuple[StatusModel, dict[str, float], float, float]:
        event_factors: dict[str, float] = {}
        for effect in self.attack_effects:
            event = automatic_value(effect, "on")
            if event in (None, "status_proc"): continue
            parent_name = self._parent_name(effect, {name: self.definitions[name] for name in names}, self.root_name)
            if parent_name is None: continue
            parent = preliminary[parent_name]
            probability = self._event_probability(effect, parent.trigger_crit_chance)
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

    def calculate_final_attacks(self, names: list[str], preliminary: dict[str, PreliminaryAttack], shared: StatusModel, status_effects: dict[str, float], random_probability: float, *, compact: bool = False) -> dict[str, AttackResult]:
        return {
            name: self.attacks.calculate(
                self.definitions[name],
                automatic_model=shared,
                status_effects=status_effects,
                random_proc_probability=random_probability if name == self.root_name else 0,
                compact=compact,
                provisional=preliminary[name].provisional,
            )
            for name in names
        }

    def derive_status_attacks(self, results: dict[str, AttackResult], names: list[str]) -> None:
        for effect in self.attack_effects:
            if automatic_value(effect, "on") != "status_proc": continue
            parent_name = self._parent_name(effect, {name: result.attack for name, result in results.items()}, self.root_name)
            if parent_name is None: continue
            if parent_name not in results: continue
            parent = results[parent_name]
            conditions = [str(condition) for condition in automatic_values(effect, "when") if str(condition).endswith("_status_proc")]
            if any(parent.effective.status_model.proc_count_per_attack(condition.removesuffix("_status_proc")) <= 0 for condition in conditions): continue
            name = self._generated_name(effect)
            if name in results: raise ValueError(f"duplicate generated attack {name!r}")
            attack = self._generated_attack(effect, parent.attack)
            parent.attack = deepcopy(parent.attack)
            if name not in parent.attack.children: parent.attack.children.append(name)
            self.definitions[parent_name] = parent.attack
            self.definitions[name] = attack
            results[name] = derive_status_attack(self.context, parent, attack, self._generated_status_types(effect))
            names.append(name)

    def derive_event_attacks(self, results: dict[str, AttackResult], names: list[str]) -> None:
        for effect in self.attack_effects:
            event = automatic_value(effect, "on")
            if event in (None, "status_proc"): continue
            parent_name = self._parent_name(effect, {name: result.attack for name, result in results.items()}, self.root_name)
            if parent_name is None: continue
            parent = results[parent_name]
            probability = self._event_probability(effect, float(parent.effective.trigger_crit_chance))
            if probability <= 0: continue
            name = self._generated_name(effect)
            if name in results: raise ValueError(f"duplicate generated attack {name!r}")
            attack = self._generated_attack(effect, parent.attack)
            parent.attack = deepcopy(parent.attack)
            if name not in parent.attack.children: parent.attack.children.append(name)
            self.definitions[parent_name] = parent.attack
            self.definitions[name] = attack
            results[name] = derive_event_attack(parent, attack, probability)
            names.append(name)

    @staticmethod
    def _event_probability(effect: ResolvedEffect, crit_chance: float) -> float:
        event = automatic_value(effect, "on")
        if event == "near_yellow_critical_hit": probability = max(1 - abs(crit_chance - 1), 0)
        elif event == "critical_hit": probability = min(max(crit_chance, 0), 1)
        elif event == "non_critical_hit": probability = max(1 - crit_chance, 0)
        else: raise ValueError(f"unsupported extra attack event {event!r}")
        chance = automatic_value(effect, "chance", 1)
        if not isinstance(chance, (int, float)) or isinstance(chance, bool): raise TypeError("extra attack chance must be numeric")
        return min(max(probability * float(chance), 0), 1)

    @staticmethod
    def _fold_metrics(output: AverageAttackStats, own: AverageAttackStats, children: list[AverageAttackStats]) -> None:
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

    def aggregate_attack_tree(self, results: dict[str, AttackResult], names: list[str], root_duration: float) -> tuple[AverageAttackStats, StatusModel, dict[str, float]]:
        root = results[self.root_name]
        group_model = StatusModel.combine([results[name].effective.status_model for name in names], root.average.attack_rate, root_duration)
        status_effects = group_model.non_damage_effects()
        status_effects["armor_reduction"] = min(status_effects.get("puncture", 0) * _special_value(root.effective.special_effects, "armor_reduction"), 1)
        aggregate = AverageAttackStats(**{name: deepcopy(getattr(root.average, name)) for name in root.average.__dataclass_fields__})
        descendants: list[str] = []

        def collect(name: str, path: frozenset[str] = frozenset()) -> None:
            if name in path: raise ValueError(f"attack relationship cycle at {name!r}")
            for child in results[name].attack.children:
                if child not in results: continue
                if child not in descendants: descendants.append(child)
                collect(child, path | {name})

        collect(self.root_name)
        self._fold_metrics(aggregate, root.average, [results[name].average for name in descendants])
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
        direct_dph = sum(float(results[name].average.flat_dph or 0) for name in names)
        dot_dph = sum(float(results[name].average.flat_dotph or 0) for name in names)
        attack_rate = float(root.average.attack_rate)
        total_dph = direct_dph + dot_dph
        weighted_damage_mass = sum((float(results[name].average.flat_dph or 0) + float(results[name].average.flat_dotph or 0)) * (float(results[name].spatial.damage_mass) if results[name].spatial.damage_mass is not None else 1.0) for name in names)
        damage_mass = weighted_damage_mass / total_dph if total_dph > 0 else 1.0
        return direct_dph, dot_dph, direct_dph * attack_rate, dot_dph * attack_rate, damage_mass

    def calculate(self) -> tuple[dict[str, AttackResult], AverageAttackStats, StatusModel, dict[str, float]]:
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


def calculate_weapon(context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> tuple[dict[str, AttackResult], AverageAttackStats, StatusModel, dict[str, float]]:
    return WeaponCalculator(context, prepared_names, prepared_upgrade_effects).calculate()


def calculate_metric_components(context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> tuple[float, float, float, float, float]:
    return WeaponCalculator(context, prepared_names, prepared_upgrade_effects).calculate_metric_components()
