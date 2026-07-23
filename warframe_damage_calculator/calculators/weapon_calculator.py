from collections.abc import Iterator

from ..fields.attack_result import AttackResult
from ..fields.calculated import AverageStats, CalculatedStats
from ..fields.upgrade import ResolvedStat
from ..fields.weapon_data import Attack
from ..models.build import Build
from ..protocols import BuildUpgradeOwner, ConfigurableWeaponOwner
from ..utils.types import Number
from . import helpers


class WeaponCalculator:
    def __init__(self, weapon: ConfigurableWeaponOwner) -> None:
        self.weapon = weapon
        self._results: dict[str, AttackResult] = {}
        self.recompute()

    @property
    def main(self) -> AttackResult:
        return self._results[self.weapon._attack]

    @property
    def child(self) -> list[AttackResult]:
        return [self._results[name] for name in self.main.children if name in self._results]

    def _resolved_build(self) -> ResolvedStat:
        build = Build(*self.weapon.build, *helpers.selected_evolution_upgrades(self.weapon))
        build.stats.resolve(self.weapon.data)
        return build.stats.total.copy()

    def _validate_attack_cycles(self) -> None:
        attacks = self.weapon.data.attacks

        def walk(name: str, ancestors: frozenset[str]) -> None:
            if name in ancestors:
                raise ValueError(f"cyclic attack relationship detected: {name}")
            if name not in attacks:
                return
            next_ancestors = ancestors | {name}
            for child in attacks[name].children:
                walk(child, next_ancestors)

        for name in attacks:
            walk(name, frozenset())

    def _walk_tree(self, name: str, ancestors: frozenset[str] | None = None) -> Iterator[AttackResult]:
        ancestors = frozenset() if ancestors is None else ancestors
        if name in ancestors:
            raise ValueError(f"cyclic attack relationship detected: {name}")
        result = self._results[name]
        yield result
        next_ancestors = ancestors | {name}
        for child in result.children:
            if child in self._results:
                yield from self._walk_tree(child, next_ancestors)

    def compute_attack(self, name: str, attack: Attack, resolved_build: ResolvedStat) -> AttackResult:
        result = AttackResult({"name": name, "attack": attack, "build": resolved_build.copy(), "children": list(attack.children)})
        self._compute_base(result)
        self._compute_modded_scalars(result)
        self._apply_condition_overload(result)
        self._compute_modded_damage(result)
        self._compute_effective(result)
        self._compute_average(result)
        return result

    def _compute_base(self, result: AttackResult) -> None:
        attack = result.attack
        ammo, stats = self.weapon.data.ammo, dict(attack.stats)
        stats.update({"attack_speed": attack.stats.fire_rate, "magazine_capacity": ammo.get("magazine_size", 1), "reload_speed": ammo.get("reload_time", 0), "recharge_rate": ammo.get("recharge_rate", 0)})
        result.base = CalculatedStats(self.weapon.stats_type(stats).with_defaults())

    def _compute_modded_scalars(self, result: AttackResult) -> None:
        build, base, modded = result.build, result.base, result.modded
        modded.multiplicative_base_damage = max(1 + build.multiplicative_base_damage, 1)
        modded.base_damage = max(1 + build.base_damage, 0)
        modded.corpus_damage = max(1 + build.corpus_damage, 1)
        modded.grineer_damage = max(1 + build.grineer_damage, 1)
        modded.infested_damage = max(1 + build.infested_damage, 1)
        modded.orokin_damage = max(1 + build.orokin_damage, 1)
        modded.murmur_damage = max(1 + build.murmur_damage, 1)
        modded.sentient_damage = max(1 + build.sentient_damage, 1)
        modded.flat_crit_chance = max(build.flat_crit_chance, 0)
        modded.multiplicative_crit_chance = max(1 + build.multiplicative_crit_chance, 1)
        modded.crit_chance = max(base.crit_chance * (1 + build.crit_chance), 0)
        modded.flat_crit_damage = max(build.flat_crit_damage, 0)
        modded.crit_damage = max(base.crit_damage * (1 + build.crit_damage), 1)
        modded.status_chance = max(base.status_chance * (1 + build.status_chance), 0)
        modded.status_damage = max(1 + build.status_damage, 1)

    def _apply_condition_overload(self, result: AttackResult) -> None:
        bonus = self._average_condition_overload_bonus(result)
        if result.attack.stats.co_effect == "multiplies":
            result.modded.multiplicative_base_damage = max(result.modded.multiplicative_base_damage + bonus, 1)
        else:
            result.modded.base_damage = max(result.modded.base_damage + bonus, 0)

    def _compute_modded_damage(self, result: AttackResult) -> None:
        damage = result.base.damage.apply(result.build.damage).combine().sorted()
        result.modded.damage = result.modded.base_damage * damage

    def _compute_effective(self, result: AttackResult) -> None:
        base, modded, effective = result.base, result.modded, result.effective
        effective.forced_procs = base.forced_procs
        effective.base_damage = modded.base_damage * modded.multiplicative_base_damage
        effective.damage = modded.multiplicative_base_damage * modded.damage
        effective.corpus_damage = modded.corpus_damage
        effective.grineer_damage = modded.grineer_damage
        effective.infested_damage = modded.infested_damage
        effective.orokin_damage = modded.orokin_damage
        effective.murmur_damage = modded.murmur_damage
        effective.sentient_damage = modded.sentient_damage
        effective.crit_chance = modded.crit_chance * modded.multiplicative_crit_chance + modded.flat_crit_chance
        effective.crit_damage = modded.crit_damage + modded.flat_crit_damage
        effective.status_chance = modded.status_chance
        effective.status_damage = modded.status_damage

    def _max_average_faction_damage(self, result: AttackResult) -> float:
        return max(result.average.corpus_damage, result.average.grineer_damage, result.average.infested_damage, result.average.orokin_damage, result.average.murmur_damage, result.average.sentient_damage)

    def _compute_average(self, result: AttackResult) -> None:
        effective, average = result.effective, result.average
        average.crit_chance = effective.crit_chance
        average.crit_multiplier = helpers.crit_multiplier(average.crit_chance, effective.crit_damage)
        average.corpus_damage = effective.corpus_damage
        average.grineer_damage = effective.grineer_damage
        average.infested_damage = effective.infested_damage
        average.orokin_damage = effective.orokin_damage
        average.murmur_damage = effective.murmur_damage
        average.sentient_damage = effective.sentient_damage

    def _flat_dotph(self, result: AttackResult, *, weakpoint: bool = False) -> float:
        return helpers.flat_dotph(result, weakpoint=weakpoint, faction_damage=self._max_average_faction_damage(result))

    def _average_condition_overload_bonus(self, result: AttackResult, time: Number = 5) -> float:
        return helpers.average_condition_overload_bonus(self.weapon, result, time)

    def _effective_attacks_per_second(self, result: AttackResult) -> float:
        return helpers.effective_attacks_per_second(self.weapon, result)

    def _fold_attack_tree(self, root: AttackResult, tree: list[AttackResult]) -> AverageStats:
        final = root.average.copy()
        final.flat_dph = sum(item.average.get("flat_dph", 0) for item in tree)
        final.flat_dotph = sum(item.average.get("flat_dotph", 0) for item in tree)
        final.total_dph = final.flat_dph + final.flat_dotph

        attack_rate = self._effective_attacks_per_second(root)
        final.flat_dps = final.flat_dph * attack_rate
        final.flat_dotps = final.flat_dotph * attack_rate
        final.total_dps = final.total_dph * attack_rate

        if any("flat_weakpoint_dph" in item.average for item in tree):
            final.flat_weakpoint_dph = sum(item.average.get("flat_weakpoint_dph", 0) for item in tree)
            final.flat_weakpoint_dotph = sum(item.average.get("flat_weakpoint_dotph", 0) for item in tree)
            final.total_weakpoint_dph = final.flat_weakpoint_dph + final.flat_weakpoint_dotph
            final.flat_weakpoint_dps = final.flat_weakpoint_dph * attack_rate
            final.flat_weakpoint_dotps = final.flat_weakpoint_dotph * attack_rate
            final.total_weakpoint_dps = final.total_weakpoint_dph * attack_rate
        return final

    def recompute(self) -> None:
        self._validate_attack_cycles()
        resolved = self._resolved_build()
        self._results = {name: self.compute_attack(name, attack, resolved) for name, attack in self.weapon.data.attacks.items()}
        for name, result in self._results.items():
            result.final = self._fold_attack_tree(result, list(self._walk_tree(name)))

    def contribution(self, upgrade: BuildUpgradeOwner) -> float:
        full = self.weapon.build
        if upgrade not in full:
            return 0.0
        reduced = full - upgrade
        full_dps = self.main.final.total_dps
        try:
            self.weapon.configure(reduced)
            return full_dps - self.main.final.total_dps
        finally:
            self.weapon.configure(full)

    def contribution_values(self) -> dict[str, float]:
        return {str(upgrade.data.name): self.contribution(upgrade) for upgrade in self.weapon.build}

    def contribution_proportions(self) -> dict[str, float]:
        contributions = self.contribution_values()
        total = sum(contributions.values()) or 1
        return {name: contribution / total for name, contribution in contributions.items()}
