from __future__ import annotations

from ..domain.results import AttackResult, AverageAttackStats, FinalAttackStats
from ..domain.status import StatusModel
from ..domain.upgrades import ResolvedEffect
from .attack_calculator import AFFLICTIONS_CATEGORIES, AttackCalculator, _product, _special_value, _status_model, _with_random_proc
from .context import CalculationContext
from .targets import ZONE_FIELDS


class WeaponCalculator:
    __slots__ = ("context", "upgrade_effects", "evolution_effects", "attacks", "root_name", "prepared_names")

    def __init__(self, context: CalculationContext, prepared_names: tuple[str, ...] | None = None) -> None:
        self.context = context
        self.upgrade_effects: tuple[ResolvedEffect, ...] = ()
        self.evolution_effects: tuple[ResolvedEffect, ...] = ()
        self.attacks: AttackCalculator
        self.root_name = context.attack
        self.prepared_names = prepared_names

    def prepare_effects(self) -> None:
        self.upgrade_effects = tuple(effect for upgrade in self.context.loadout.upgrades if upgrade.implemented for effect in upgrade.resolve_manual())
        self.evolution_effects = tuple(effect for perk in self.context.resolved_perks for effect in perk.effects)
        self.attacks = AttackCalculator(self.context, self.upgrade_effects, self.evolution_effects)

    def collect_attack_tree(self) -> list[str]:
        ordered: list[str] = []

        def collect(name: str, path: frozenset[str] = frozenset()) -> None:
            if name in path: raise ValueError(f"attack relationship cycle at {name!r}")
            if name not in self.context.weapon.attacks: raise ValueError(f"unknown child attack {name!r}")
            if name in ordered: return
            ordered.append(name)
            for child in self.context.weapon.attacks[name].children: collect(child, path | {name})

        collect(self.root_name)
        return ordered

    def calculate_preliminary_attacks(self, names: list[str]) -> dict[str, AttackResult]:
        return {name: self.attacks.calculate(self.context.weapon.attacks[name]) for name in names}

    def build_shared_status_model(self, preliminary: dict[str, AttackResult], names: list[str]) -> tuple[StatusModel, dict[str, float], float, float]:
        preliminary_models = [preliminary[name].effective.status_model for name in names]
        root_rate = preliminary[self.root_name].average.sustained_fire_rate
        root_duration = max((model.duration for model in preliminary_models), default=0)
        random_probabilities: list[float] = []
        for name in names:
            result = preliminary[name]
            effects = result.effective.special_effects
            model = _status_model(result.effective.damage, result.effective.forced_procs, float(result.effective.status_chance), float(result.effective.multishot), result.average.sustained_fire_rate, float(result.effective.status_duration), effects, result.average.crit_chance, afflictions=bool(AFFLICTIONS_CATEGORIES & set(result.effective.forced_procs)))
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
    def _fold_metrics(output: FinalAttackStats, own: AverageAttackStats, children: list[AverageAttackStats]) -> None:
        for fields in ZONE_FIELDS.values():
            direct_values = [getattr(own, fields[0]), *(getattr(child, fields[0]) for child in children)]
            dot_values = [getattr(own, fields[1]), *(getattr(child, fields[1]) for child in children)]
            if not any(value is not None for value in (*direct_values, *dot_values)):
                for field in fields: setattr(output, field, None)
                continue
            direct = sum(float(value or 0) for value in direct_values)
            dot = sum(float(value or 0) for value in dot_values)
            setattr(output, fields[0], direct)
            setattr(output, fields[1], dot)
            setattr(output, fields[2], direct + dot)
            setattr(output, fields[3], direct * own.sustained_fire_rate)
            setattr(output, fields[4], dot * own.sustained_fire_rate)
            setattr(output, fields[5], (direct + dot) * own.sustained_fire_rate)

    def fold_attack_tree(self, results: dict[str, AttackResult], names: list[str], root_duration: float) -> None:
        root = results[self.root_name]
        final_group_model = StatusModel.combine([results[name].effective.status_model for name in names], root.average.sustained_fire_rate, root_duration)
        root.average.procs_per_shot = final_group_model.expected_procs_per_attack
        root.final.procs_per_shot = final_group_model.expected_procs_per_attack
        root.status_effects = final_group_model.non_damage_effects()
        root.status_effects["armor_reduction"] = min(root.status_effects.get("puncture", 0) * _special_value(root.effective.special_effects, "armor_reduction"), 1)

        def descendants(name: str, path: frozenset[str] = frozenset()) -> list[str]:
            if name in path: raise ValueError(f"attack relationship cycle at {name!r}")
            collected: list[str] = []
            for child in results[name].children:
                if child not in collected: collected.append(child)
                for descendant in descendants(child, path | {name}):
                    if descendant not in collected: collected.append(descendant)
            return collected

        for name, result in results.items():
            child_names = descendants(name)
            self._fold_metrics(result.final, result.average, [results[child].average for child in child_names])

    def calculate(self) -> dict[str, AttackResult]:
        self.prepare_effects()
        names = list(self.prepared_names) if self.prepared_names is not None else self.collect_attack_tree()
        preliminary = self.calculate_preliminary_attacks(names)
        shared, status_effects, random_probability, root_duration = self.build_shared_status_model(preliminary, names)
        results = self.calculate_final_attacks(names, shared, status_effects, random_probability)
        self.fold_attack_tree(results, names, root_duration)
        return results


def calculate_weapon(context: CalculationContext, prepared_names: tuple[str, ...] | None = None) -> dict[str, AttackResult]:
    return WeaponCalculator(context, prepared_names).calculate()
