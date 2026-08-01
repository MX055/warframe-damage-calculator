from __future__ import annotations

from copy import deepcopy

from ..domain.status import StatusModel, _product
from ..domain.upgrades import ResolvedEffect
from .attack_calculator import AttackCalculator
from .context import CalculationContext
from .models.attack import AttackResult, AverageAttackStats
from .status import AFFLICTIONS_CATEGORIES, _special_value, _status_model, _with_random_proc


class WeaponCalculator:
    __slots__ = ("context", "upgrade_effects", "evolution_effects", "attacks", "root_name", "prepared_names", "prepared_upgrade_effects")

    def __init__(self, context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> None:
        self.context = context
        self.upgrade_effects: tuple[ResolvedEffect, ...] = ()
        self.evolution_effects: tuple[ResolvedEffect, ...] = ()
        self.attacks: AttackCalculator
        self.root_name = context.attack
        self.prepared_names = prepared_names
        self.prepared_upgrade_effects = prepared_upgrade_effects

    def prepare_effects(self) -> None:
        self.upgrade_effects = self.prepared_upgrade_effects if self.prepared_upgrade_effects is not None else tuple(effect for upgrade in self.context.loadout.ranked_upgrades if upgrade.implemented for effect in upgrade.resolve_manual())
        self.evolution_effects = tuple(effect for perk in self.context.resolved_perks for effect in perk.effects)
        self.attacks = AttackCalculator(self.context, self.upgrade_effects, self.evolution_effects)

    def collect_attack_tree(self) -> list[str]:
        ordered: list[str] = []
        equipped = {upgrade.name for upgrade in self.context.loadout.ranked_upgrades}

        def collect(name: str, path: frozenset[str] = frozenset()) -> None:
            if name in path: raise ValueError(f"attack relationship cycle at {name!r}")
            if name not in self.context.weapon.attacks: raise ValueError(f"unknown child attack {name!r}")
            generated_by = self.context.weapon.attacks[name].generated_by
            if generated_by is not None and generated_by not in equipped:
                if name == self.root_name: raise ValueError(f"attack {name!r} requires {generated_by}")
                return
            if name in ordered: return
            ordered.append(name)
            for child in self.context.weapon.attacks[name].children: collect(child, path | {name})

        collect(self.root_name)
        return ordered

    def calculate_preliminary_attacks(self, names: list[str]) -> dict[str, AttackResult]:
        return {name: self.attacks.calculate(self.context.weapon.attacks[name]) for name in names}

    def build_shared_status_model(self, preliminary: dict[str, AttackResult], names: list[str]) -> tuple[StatusModel, dict[str, float], float, float]:
        preliminary_models = [preliminary[name].effective.status_model for name in names]
        root_rate = preliminary[self.root_name].average.attack_rate
        root_duration = max((model.duration for model in preliminary_models), default=0)
        random_probabilities: list[float] = []
        for name in names:
            result = preliminary[name]
            effects = result.effective.special_effects
            model = _status_model(result.effective.damage, result.effective.forced_procs, float(result.effective.status_chance), float(result.effective.multishot), result.average.attack_rate, float(result.effective.status_duration), effects, result.average.crit_chance, afflictions=bool(AFFLICTIONS_CATEGORIES & set(result.effective.forced_procs)))
            random_probabilities.append(model.random_proc_probability)
        random_probability = 1 - _product(1 - probability for probability in random_probabilities)
        shared = StatusModel.combine(preliminary_models, root_rate, root_duration)
        shared = _with_random_proc(shared, preliminary[self.root_name].effective.special_effects, random_probability)
        return shared, shared.non_damage_effects(), random_probability, root_duration

    def calculate_final_attacks(self, names: list[str], shared: StatusModel, status_effects: dict[str, float], random_probability: float) -> dict[str, AttackResult]:
        return {
            name: self.attacks.calculate(
                self.context.weapon.attacks[name],
                automatic_model=shared,
                status_effects=status_effects,
                random_proc_probability=random_probability if name == self.root_name else 0,
            )
            for name in names
        }

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
        names = list(self.prepared_names) if self.prepared_names is not None else self.collect_attack_tree()
        preliminary = self.calculate_preliminary_attacks(names)
        shared, status_effects, random_probability, _ = self.build_shared_status_model(preliminary, names)
        results = self.calculate_final_attacks(names, shared, status_effects, random_probability)
        root = results[self.root_name]
        direct_dph = sum(float(results[name].average.flat_dph or 0) for name in names)
        dot_dph = sum(float(results[name].average.flat_dotph or 0) for name in names)
        attack_rate = float(root.average.attack_rate)
        damage_mass = float(root.spatial.damage_mass) if root.spatial.damage_mass is not None else 1.0
        return direct_dph, dot_dph, direct_dph * attack_rate, dot_dph * attack_rate, damage_mass

    def calculate(self) -> tuple[dict[str, AttackResult], AverageAttackStats, StatusModel, dict[str, float]]:
        self.prepare_effects()
        names = list(self.prepared_names) if self.prepared_names is not None else self.collect_attack_tree()
        preliminary = self.calculate_preliminary_attacks(names)
        shared, status_effects, random_probability, root_duration = self.build_shared_status_model(preliminary, names)
        results = self.calculate_final_attacks(names, shared, status_effects, random_probability)
        aggregate, aggregate_status_model, aggregate_status_effects = self.aggregate_attack_tree(results, names, root_duration)
        return results, aggregate, aggregate_status_model, aggregate_status_effects


def calculate_weapon(context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> tuple[dict[str, AttackResult], AverageAttackStats, StatusModel, dict[str, float]]:
    return WeaponCalculator(context, prepared_names, prepared_upgrade_effects).calculate()


def calculate_metric_components(context: CalculationContext, prepared_names: tuple[str, ...] | None = None, prepared_upgrade_effects: tuple[ResolvedEffect, ...] | None = None) -> tuple[float, float, float, float, float]:
    return WeaponCalculator(context, prepared_names, prepared_upgrade_effects).calculate_metric_components()
