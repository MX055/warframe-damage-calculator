from collections.abc import Callable, Iterator, Mapping
from math import expm1, factorial, log1p

from ..fields.attack_result import AttackResult
from ..fields.calculated import AverageStats, CalculatedStats
from ..fields.evolution import ConversionBonus, ResolvedEvolutionStat
from ..fields.upgrade import ResolvedStat
from ..fields.weapon_data import Attack
from ..models.data import Data
from ..models.dist import Dist
from ..protocols import ConfigurableWeaponOwner
from ..utils.constants import DOT_MULTIPLIERS
from ..utils.types import Number
from .evolution_calculator import EvolutionCalculator
from .upgrade_calculator import UpgradeCalculator


class WeaponCalculator:
    main: AttackResult
    child: list[AttackResult]

    def __init__(self, weapon: ConfigurableWeaponOwner) -> None:
        self.weapon = weapon
        self.resolve()

    @staticmethod
    def _crit_multiplier(crit_chance: Number, crit_damage: Number) -> float:
        return 1 + crit_chance * (crit_damage - 1)

    @staticmethod
    def _non_crit_bonus(damage: Number = 0, chance: Number = 0) -> float:
        damage = float(damage or 0)
        if not damage:
            return 0.0
        chance = float(chance or 0)
        return damage * (chance if chance else 1.0)

    @staticmethod
    def _hit_multiplier(crit_chance: Number, crit_damage: Number, non_crit_bonus_damage: Number = 0, non_crit_bonus_chance: Number = 0) -> float:
        bonus = WeaponCalculator._non_crit_bonus(non_crit_bonus_damage, non_crit_bonus_chance)
        return WeaponCalculator._crit_multiplier(crit_chance, crit_damage) + max(0.0, 1.0 - float(crit_chance)) * bonus

    @staticmethod
    def _combine_chance(additive: Number, multiplicative: Number = 1, flat: Number = 0) -> Number:
        return max(additive * multiplicative + flat, 0)

    @staticmethod
    def _refresh_dps_from_dph(average: AverageStats) -> None:
        average.flat_dps = average.fire_rate * average.flat_dph
        average.flat_weakpoint_dps = average.fire_rate * average.flat_weakpoint_dph
        average.total_dph = average.flat_dph + average.flat_dotph
        average.total_weakpoint_dph = average.flat_weakpoint_dph + average.flat_weakpoint_dotph
        average.total_dps = average.flat_dps + average.flat_dotps
        average.total_weakpoint_dps = average.flat_weakpoint_dps + average.flat_weakpoint_dotps

    def _resolved_build(self) -> ResolvedStat:
        build = self.weapon.build
        build.results.resolve(self.weapon.data)
        return build.results.total

    def _resolved_evolutions(self) -> ResolvedEvolutionStat:
        if not self.weapon._evolutions:
            return ResolvedEvolutionStat()
        return EvolutionCalculator(self.weapon).total

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

    def _walk_tree(self, name: str, results: Mapping[str, AttackResult], ancestors: frozenset[str] | None = None) -> Iterator[AttackResult]:
        ancestors = frozenset() if ancestors is None else ancestors
        if name in ancestors:
            raise ValueError(f"cyclic attack relationship detected: {name}")
        result = results[name]
        yield result
        next_ancestors = ancestors | {name}
        for child in result.children:
            if child in results:
                yield from self._walk_tree(child, results, next_ancestors)

    def _compute_attack(self, name: str, attack: Attack, resolved_build: ResolvedStat, resolved_evolutions: ResolvedEvolutionStat) -> AttackResult:
        result = AttackResult({"name": name, "attack": attack, "build": resolved_build, "evolutions": resolved_evolutions, "children": list(attack.children)})
        self._compute_base(result)
        self._compute_modded_scalars(result)
        self._apply_condition_overload(result)
        self._compute_modded_damage(result)
        self._compute_effective(result)
        self._apply_evolution_conversions(result)
        self._compute_average(result)
        return result

    @staticmethod
    def _distribute_flat_damage(damage: Dist, flat: Number) -> Dist:
        return Dist({damage_type: flat * damage.weight(damage_type) for damage_type, _ in damage})

    def _compute_base(self, result: AttackResult) -> None:
        attack = result.attack
        ammo, stats = self.weapon.data.ammo, dict(attack.stats)
        falloff = stats.pop("falloff", None) or {}
        stats.update({"attack_speed": attack.stats.fire_rate, "magazine_capacity": ammo.get("magazine_size", 1), "reload_speed": ammo.get("reload_time", 0), "recharge_rate": ammo.get("recharge_rate", 0)})
        if falloff:
            stats.update({"start_range": falloff.get("start_range", 0), "end_range": falloff.get("end_range", 0), "final_multiplier": falloff.get("final_multiplier", 1)})
        result.base = CalculatedStats(self.weapon.stats_type(stats).with_defaults())
        result.original_damage = Dist(dict(result.base.damage))

        evo = result.evolutions.base
        added = float(evo.get("damage", 0) or 0)
        if added: result.base.damage = result.base.damage + self._distribute_flat_damage(result.base.damage, added)
        result.base.crit_chance = max(float(result.base.get("crit_chance", 0) or 0) + float(evo.get("crit_chance", 0) or 0), 0)
        result.base.crit_damage = max(float(result.base.get("crit_damage", 0) or 0) + float(evo.get("crit_damage", 0) or 0), 1)
        result.base.status_chance = max(float(result.base.get("status_chance", 0) or 0) + float(evo.get("status_chance", 0) or 0), 0)
        result.base.magazine_capacity = max(float(result.base.get("magazine_capacity", 0) or 0) + float(evo.get("magazine_capacity", 0) or 0), 1)

    def _compute_modded_scalars(self, result: AttackResult) -> None:
        build, evo, base, modded = result.build, result.evolutions, result.base, result.modded
        modded.multiplicative.damage_bonus = max(1 + build.multiplicative.damage_bonus, 1)
        modded.additive.damage_bonus = max(1 + build.additive.damage_bonus + evo.additive.damage_bonus, 0)
        modded.additive.corpus_damage = max(1 + build.additive.corpus_damage, 1)
        modded.additive.grineer_damage = max(1 + build.additive.grineer_damage, 1)
        modded.additive.infested_damage = max(1 + build.additive.infested_damage, 1)
        modded.additive.orokin_damage = max(1 + build.additive.orokin_damage, 1)
        modded.additive.murmur_damage = max(1 + build.additive.murmur_damage, 1)
        modded.additive.sentient_damage = max(1 + build.additive.sentient_damage, 1)
        modded.flat.crit_chance = build.flat.crit_chance + evo.flat.crit_chance
        modded.multiplicative.crit_chance = max(1 + build.multiplicative.crit_chance, 1)
        modded.additive.crit_chance = max(base.crit_chance * (1 + build.additive.crit_chance), 0)
        modded.flat.crit_damage = max(build.flat.crit_damage + evo.flat.crit_damage, 0)
        modded.additive.crit_damage = max(base.crit_damage * (1 + build.additive.crit_damage), 1)
        modded.flat.status_chance = build.flat.status_chance + evo.flat.status_chance
        modded.additive.status_chance = max(base.status_chance * (1 + build.additive.status_chance + evo.additive.status_chance), 0)
        modded.additive.status_damage = max(1 + build.additive.status_damage, 1)
        modded.additive.non_crit_bonus_damage = max(build.additive.non_crit_bonus_damage + evo.additive.non_crit_bonus_damage, 0)
        modded.additive.non_crit_bonus_chance = max(build.additive.non_crit_bonus_chance, evo.additive.non_crit_bonus_chance, 0)

    def _average_condition_overload_bonus(self, result: AttackResult, time: Number = 5) -> float:
        build, stats = result.build, result.attack.stats
        # GunCO / CO scales off original (pre-evolution) base damage only.
        damage = result.original_damage.apply(build.additive.damage).combine().sorted()
        guaranteed, fractional = divmod(max(stats.status_chance * (1 + build.additive.status_chance + result.evolutions.additive.status_chance) + result.modded.flat.status_chance, 0), 1)
        guaranteed_hits, fractional_hit = divmod(max(self._status_hits(result), 0), 1)
        probabilities: dict[str, float] = {}
        for damage_type in damage.data:
            weight = damage.weight(damage_type)
            miss = (1 - weight) ** guaranteed * (1 - fractional * weight)
            probabilities[damage_type] = 1 - miss ** guaranteed_hits * (1 - fractional_hit + fractional_hit * miss)
        probabilities.update({damage_type: 1.0 for damage_type, count in stats.forced_procs if count > 0})

        condition_overload = build.additive.condition_overload
        maximum = len(probabilities) if condition_overload.max_stacks == "inf" else int(condition_overload.max_stacks)
        attack_rate = self._effective_attacks_per_second(result)
        if maximum <= 0 or attack_rate <= 0:
            return 0.0
        attempts, distribution = attack_rate * time, [1.0] + [0.0] * maximum
        for probability in probabilities.values():
            acquired = 0 if probability <= 0 else 1 if probability >= 1 else -expm1(attempts * log1p(-probability))
            updated = [0.0] * (maximum + 1)
            for count, chance in enumerate(distribution):
                updated[count] += chance * (1 - acquired)
                updated[min(count + 1, maximum)] += chance * acquired
            distribution = updated
        expected = sum(count * chance for count, chance in enumerate(distribution))
        return float(condition_overload.value) * stats.co_factor * expected

    def _apply_condition_overload(self, result: AttackResult) -> None:
        bonus = self._average_condition_overload_bonus(result)
        if result.attack.stats.co_effect == "multiplies":
            result.modded.multiplicative.damage_bonus = max(result.modded.multiplicative.damage_bonus + bonus, 1)
        else:
            result.modded.additive.damage_bonus = max(result.modded.additive.damage_bonus + bonus, 0)

    def _compute_modded_damage(self, result: AttackResult) -> None:
        build = result.build
        evolved = result.base.damage.apply(build.additive.damage).combine().sorted()
        original = result.original_damage.apply(build.additive.damage).combine().sorted()
        serration = max(1 + build.additive.damage_bonus + result.evolutions.additive.damage_bonus, 0)
        if result.attack.stats.co_effect == "multiplies":
            result.modded.additive.damage = result.modded.additive.damage_bonus * evolved
        else:
            # GunCO / additive CO scales original (pre-evolution) damage only; Serration scales evolved.
            co_bonus = max(float(result.modded.additive.damage_bonus) - serration, 0)
            result.modded.additive.damage = serration * evolved + co_bonus * original

    def _compute_effective(self, result: AttackResult) -> None:
        base, modded, effective = result.base, result.modded, result.effective
        effective.forced_procs = base.forced_procs
        effective.damage_bonus = modded.additive.damage_bonus * modded.multiplicative.damage_bonus
        effective.damage = modded.multiplicative.damage_bonus * modded.additive.damage
        effective.corpus_damage = modded.additive.corpus_damage
        effective.grineer_damage = modded.additive.grineer_damage
        effective.infested_damage = modded.additive.infested_damage
        effective.orokin_damage = modded.additive.orokin_damage
        effective.murmur_damage = modded.additive.murmur_damage
        effective.sentient_damage = modded.additive.sentient_damage
        effective.crit_chance = self._combine_chance(modded.additive.crit_chance, modded.multiplicative.crit_chance, modded.flat.crit_chance)
        effective.crit_damage = modded.additive.crit_damage + modded.flat.crit_damage
        effective.status_chance = self._combine_chance(modded.additive.status_chance, flat=modded.flat.status_chance)
        effective.status_damage = modded.additive.status_damage
        effective.non_crit_bonus_damage = modded.additive.non_crit_bonus_damage
        effective.non_crit_bonus_chance = modded.additive.non_crit_bonus_chance

    def _refresh_crit_scalars(self, result: AttackResult) -> None:
        build, base, modded, effective = result.build, result.base, result.modded, result.effective
        modded.additive.crit_chance = max(base.crit_chance * (1 + build.additive.crit_chance), 0)
        effective.crit_chance = self._combine_chance(modded.additive.crit_chance, modded.multiplicative.crit_chance, modded.flat.crit_chance)
        if "weakpoint_crit_chance" in modded.additive:
            modded.additive.weakpoint_crit_chance = max(base.crit_chance * (1 + build.additive.crit_chance + build.additive.weakpoint_crit_chance), 0)
            effective.weakpoint_crit_chance = self._combine_chance(modded.additive.weakpoint_crit_chance, modded.multiplicative.crit_chance + modded.multiplicative.weakpoint_crit_chance - 1, modded.flat.crit_chance)

    def _refresh_status_scalars(self, result: AttackResult) -> None:
        build, evo, base, modded, effective = result.build, result.evolutions, result.base, result.modded, result.effective
        modded.additive.status_chance = max(base.status_chance * (1 + build.additive.status_chance + evo.additive.status_chance), 0)
        effective.status_chance = self._combine_chance(modded.additive.status_chance, flat=modded.flat.status_chance)

    def _apply_evolution_conversions(self, result: AttackResult) -> None:
        evo = result.evolutions
        crit_from = evo.additive.get("crit_from_status")
        if isinstance(crit_from, ConversionBonus) and float(crit_from.value):
            cap = float(crit_from.max) if float(crit_from.max) else float("inf")
            bonus = min(cap, float(crit_from.value) * float(result.effective.status_chance))
            result.base.crit_chance = max(float(result.base.crit_chance) + bonus, 0)
            self._refresh_crit_scalars(result)

        status_from = evo.additive.get("status_from_crit")
        if isinstance(status_from, ConversionBonus) and float(status_from.value):
            cap = float(status_from.max) if float(status_from.max) else float("inf")
            bonus = min(cap, float(status_from.value) * float(result.effective.crit_chance))
            result.base.status_chance = max(float(result.base.status_chance) + bonus, 0)
            self._refresh_status_scalars(result)

    def _max_average_faction_damage(self, result: AttackResult) -> float:
        return max(result.average.corpus_damage, result.average.grineer_damage, result.average.infested_damage, result.average.orokin_damage, result.average.murmur_damage, result.average.sentient_damage)

    def _compute_average(self, result: AttackResult) -> None:
        effective, average = result.effective, result.average
        average.crit_chance = effective.crit_chance
        average.crit_multiplier = self._crit_multiplier(average.crit_chance, effective.crit_damage)
        average.corpus_damage = effective.corpus_damage
        average.grineer_damage = effective.grineer_damage
        average.infested_damage = effective.infested_damage
        average.orokin_damage = effective.orokin_damage
        average.murmur_damage = effective.murmur_damage
        average.sentient_damage = effective.sentient_damage

    @staticmethod
    def _status_hits(result: AttackResult) -> float:
        build, stats, modded = result.build, result.attack.stats, result.modded
        hits = max(modded.additive.get("multishot", stats.multishot), 1)
        duplicate = modded.additive.get("melee_duplicate", 0)
        chance = max(stats.crit_chance * (1 + build.additive.crit_chance) * modded.multiplicative.crit_chance + modded.flat.crit_chance, 0)
        return hits + duplicate * max(0, 1 - abs(chance - 1))

    def _effective_attacks_per_second(self, result: AttackResult) -> float:
        stats, base, modded = result.attack.stats, result.base, result.modded
        if "attack_speed" in modded.additive:
            return max(stats.fire_rate * modded.additive.attack_speed / (base.attack_speed or 1), 0)
        if "magazine_capacity" not in modded.additive:
            return max(stats.fire_rate, 0)

        build, evo = result.build, result.evolutions
        speed = 1 if build.additive.fire_rate_lock else max(1 + build.additive.fire_rate + evo.additive.fire_rate, 0.01)
        fire_rate = max(stats.fire_rate * speed, 0.05) * modded.multiplicative.fire_rate
        burst_count = max(stats.burst_count, 1)
        ammo_cost = max(float(modded.additive.get("ammo_cost", stats.ammo_cost)), 0)
        if ammo_cost <= 0:
            return fire_rate
        shots = modded.additive.magazine_capacity / ammo_cost
        bursts = shots / burst_count
        is_battery = "recharge_delay" in self.weapon.data.ammo
        reload_speed = modded.additive.reload_speed + (0 if not is_battery else float("inf") if modded.additive.recharge_rate <= 0 else modded.additive.magazine_capacity / modded.additive.recharge_rate)
        ammo_spent = 1 - modded.additive.ammo_efficiency
        cycle = bursts * (max(stats.charge_time, 0) / speed / modded.multiplicative.fire_rate + (burst_count - 1) * max(stats.burst_delay, 0) / max(speed, 1))
        cycle += (bursts - ammo_spent) / fire_rate + ammo_spent * reload_speed
        return float("inf") if cycle <= 0 else shots / cycle

    def _flat_dotph(self, result: AttackResult, *, weakpoint: bool = False, hits: Number | None = None, damage_multiplier: Number = 1, extra_damage: Number = 0, faction_damage: Number | None = None) -> float:
        if faction_damage is None:
            faction_damage = self._max_average_faction_damage(result)
        base, effective, average = result.base, result.effective, result.average
        if effective.damage.total_damage() <= 0:
            return 0.0
        multiplier = self._hit_multiplier(average.weakpoint_crit_chance if weakpoint else average.crit_chance, effective.crit_damage, effective.get("non_crit_bonus_damage", 0), effective.get("non_crit_bonus_chance", 0))
        regular = sum(factor * effective.damage.get(damage_type) * effective.damage.weight(damage_type) for damage_type, factor in DOT_MULTIPLIERS) * effective.status_chance
        forced = sum(factor * base.forced_procs.get(damage_type) * effective.damage.get(damage_type) for damage_type, factor in DOT_MULTIPLIERS)
        shot_hits = effective.get("multishot", self._status_hits(result)) if hits is None else hits
        return (regular + forced) * effective.status_damage * faction_damage ** 2 * multiplier * damage_multiplier * shot_hits + extra_damage

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

    def _needed_attack_names(self) -> set[str]:
        attacks = self.weapon.data.attacks
        needed = {self.weapon._attack}
        pending = [self.weapon._attack]
        while pending:
            name = pending.pop()
            attack = attacks.get(name)
            if attack is None:
                continue
            for child in attack.children:
                if child not in needed and child in attacks:
                    needed.add(child)
                    pending.append(child)
        return needed

    def _total_dps(self, resolved_build: ResolvedStat, resolved_evolutions: ResolvedEvolutionStat) -> float:
        attacks = self.weapon.data.attacks
        needed = self._needed_attack_names()
        results = {name: self._compute_attack(name, attacks[name], resolved_build, resolved_evolutions) for name in needed}
        for name, result in results.items():
            result.final = self._fold_attack_tree(result, list(self._walk_tree(name, results)))
        return float(results[self.weapon._attack].final.total_dps)

    def resolve(self, *, validate_cycles: bool = True) -> None:
        if validate_cycles:
            self._validate_attack_cycles()
        resolved_build = self._resolved_build()
        resolved_evolutions = self._resolved_evolutions()
        attacks = self.weapon.data.attacks
        needed = self._needed_attack_names()
        results = {name: self._compute_attack(name, attacks[name], resolved_build, resolved_evolutions) for name in needed}
        for name, result in results.items():
            result.final = self._fold_attack_tree(result, list(self._walk_tree(name, results)))
        self.main = results[self.weapon._attack]
        self.child = [results[name] for name in self.main.children if name in results]

    @staticmethod
    def _upgrade_depends_on_equipped(upgrade) -> bool:
        return any(effect.equipped is not None for effect in upgrade.results._normalize_effects())

    def _coalition_total_lookup(self) -> tuple[list[str], int, Callable[[int, int], ResolvedStat], ResolvedEvolutionStat]:
        upgrades = list(self.weapon.build)
        count = len(upgrades)
        names = [str(upgrade.data.name or "") for upgrade in upgrades]
        weapon_data = self.weapon.data
        resolved_evolutions = self._resolved_evolutions()
        depends_on_equipped = [self._upgrade_depends_on_equipped(upgrade) for upgrade in upgrades]
        cached_totals: list[ResolvedStat | None] = [None] * count
        modular_totals: dict[tuple[int, int], ResolvedStat] = {}

        for index, upgrade in enumerate(upgrades):
            if depends_on_equipped[index]:
                continue
            upgrade.results.resolve(weapon_data, Data({"equipped": names}))
            cached_totals[index] = upgrade.results.total

        def total_for(index: int, mask: int) -> ResolvedStat:
            cached = cached_totals[index]
            if cached is not None:
                return cached
            key = (index, mask)
            cached = modular_totals.get(key)
            if cached is None:
                equipped = [names[other] for other in range(count) if mask & (1 << other)]
                upgrades[index].results.resolve(weapon_data, Data({"equipped": equipped}))
                cached = upgrades[index].results.total
                modular_totals[key] = cached
            return cached

        return names, count, total_for, resolved_evolutions

    def _dps_for_coalition(self, mask: int, count: int, total_for: Callable[[int, int], ResolvedStat], resolved_evolutions: ResolvedEvolutionStat) -> float:
        resolved_build = ResolvedStat()
        for index in range(count):
            if mask & (1 << index):
                UpgradeCalculator._merge_resolved_stat(resolved_build, total_for(index, mask))
        return self._total_dps(resolved_build, resolved_evolutions)

    def removal_contributions(self) -> dict[str, float]:
        if not self.weapon.build:
            return {}

        names, count, total_for, resolved_evolutions = self._coalition_total_lookup()
        full_mask = (1 << count) - 1
        full_dps = self._dps_for_coalition(full_mask, count, total_for, resolved_evolutions)
        return {names[index]: full_dps - self._dps_for_coalition(full_mask ^ (1 << index), count, total_for, resolved_evolutions) for index in range(count)}

    def shapley_contributions(self) -> dict[str, float]:
        if not self.weapon.build:
            return {}

        names, count, total_for, resolved_evolutions = self._coalition_total_lookup()
        coalition_dps = [self._dps_for_coalition(mask, count, total_for, resolved_evolutions) for mask in range(1 << count)]

        contributions = [0.0] * count
        denominator = factorial(count)
        for mask in range(1 << count):
            size = mask.bit_count()
            if size == count:
                continue
            weight = factorial(size) * factorial(count - size - 1) / denominator
            baseline = coalition_dps[mask]
            for index in range(count):
                bit = 1 << index
                if mask & bit:
                    continue
                contributions[index] += weight * (coalition_dps[mask | bit] - baseline)

        total = sum(contributions) or 1
        return {names[index]: contributions[index] / total for index in range(count)}
