from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from ..domain.status import StatusModel, _product
from ..domain.upgrades import ResolvedEffect
from ..domain.weapons import Attack, AttackStats
from .attack_calculator import AttackCalculator, derive_status_attack
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
    def _attack_record(effect: ResolvedEffect) -> tuple[str | None, Mapping[str, object]]:
        if not isinstance(effect.value, Mapping): raise TypeError("extra_attack value must be an object")
        attack = effect.value.get("attack")
        if not isinstance(attack, Mapping): raise TypeError("extra_attack.attack must be an object")
        parent = effect.value.get("parent")
        if parent is not None and not isinstance(parent, str): raise TypeError("extra_attack.parent must be a string")
        return parent, attack

    @staticmethod
    def _template_value(value: object, inherited: object, parent: Attack) -> object:
        if value == "$attack": return deepcopy(inherited)
        if isinstance(value, Mapping) and "source" in value:
            if set(value) - {"source", "multiplier"}: raise ValueError("attack source expressions only support source and multiplier")
            source = value["source"]
            if source == "$attack.damage.total": resolved = parent.stats.damage.total
            elif source == "$attack": resolved = inherited
            else: raise ValueError(f"unknown attack template source {source!r}")
            multiplier = value.get("multiplier", 1)
            if not isinstance(resolved, (int, float)) or not isinstance(multiplier, (int, float)): raise TypeError("attack source expressions must resolve to numbers")
            return float(resolved) * float(multiplier)
        return deepcopy(value)

    @classmethod
    def _generated_attack(cls, effect: ResolvedEffect, parent: Attack) -> Attack:
        _, template = cls._attack_record(effect)
        name = template.get("name")
        if not isinstance(name, str) or not name: raise ValueError("extra_attack.attack.name is required")
        values: dict[str, object] = {"name": name, "generated_by": effect.source}
        for field_name in ("trigger", "delivery", "form", "category", "aoe", "children"):
            if field_name in template: values[field_name] = cls._template_value(template[field_name], getattr(parent, field_name), parent)
        stats_template = template.get("stats", {})
        if not isinstance(stats_template, Mapping): raise TypeError("extra_attack.attack.stats must be an object")
        stats: dict[str, object] = {}
        for field_name, value in stats_template.items():
            if field_name in {"damage", "forced_procs", "falloff"}:
                if not isinstance(value, Mapping): raise TypeError(f"extra_attack.attack.stats.{field_name} must be an object")
                inherited = parent.stats.falloff if field_name == "falloff" else getattr(parent.stats, field_name)
                stats[field_name] = {key: cls._template_value(item, inherited.get(key, 0), parent) for key, item in value.items()}
            else:
                if not hasattr(parent.stats, field_name): raise ValueError(f"unknown attack stat {field_name!r}")
                stats[field_name] = cls._template_value(value, getattr(parent.stats, field_name), parent)
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
            if automatic_value(effect, "on") == "status_proc": continue
            configured_parent, _ = self._attack_record(effect)
            parent_name = configured_parent or self.root_name
            if parent_name not in self.definitions: raise ValueError(f"unknown generated attack parent {parent_name!r}")
            name = self._generated_name(effect)
            if name in self.definitions: raise ValueError(f"duplicate generated attack {name!r}")
            parent = deepcopy(self.definitions[parent_name])
            if name not in parent.children: parent.children.append(name)
            self.definitions[parent_name] = parent
            self.definitions[name] = self._generated_attack(effect, parent)

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
        preliminary_models = [preliminary[name].status_model for name in names]
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
            configured_parent, _ = self._attack_record(effect)
            parent_name = configured_parent or self.root_name
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
        root = results[self.root_name]
        direct_dph = sum(float(results[name].average.flat_dph or 0) for name in names)
        dot_dph = sum(float(results[name].average.flat_dotph or 0) for name in names)
        attack_rate = float(root.average.attack_rate)
        damage_mass = float(root.spatial.damage_mass) if root.spatial.damage_mass is not None else 1.0
        return direct_dph, dot_dph, direct_dph * attack_rate, dot_dph * attack_rate, damage_mass

    def calculate(self) -> tuple[dict[str, AttackResult], AverageAttackStats, StatusModel, dict[str, float]]:
        self.prepare_effects()
        collected = self.collect_attack_tree()
        names = list(self.prepared_names) if self.prepared_names is not None else collected
        preliminary = self.calculate_preliminary_attacks(names)
        shared, status_effects, random_probability, root_duration = self.build_shared_status_model(preliminary, names)
        results = self.calculate_final_attacks(names, preliminary, shared, status_effects, random_probability)
        self.derive_status_attacks(results, names)
        aggregate, aggregate_status_model, aggregate_status_effects = self.aggregate_attack_tree(results, names, root_duration)
        return results, aggregate, aggregate_status_model, aggregate_status_effects


def calculate_weapon(context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> tuple[dict[str, AttackResult], AverageAttackStats, StatusModel, dict[str, float]]:
    return WeaponCalculator(context, prepared_names, prepared_upgrade_effects).calculate()


def calculate_metric_components(context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> tuple[float, float, float, float, float]:
    return WeaponCalculator(context, prepared_names, prepared_upgrade_effects).calculate_metric_components()
