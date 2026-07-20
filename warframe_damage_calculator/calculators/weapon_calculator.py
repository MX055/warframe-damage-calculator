from math import expm1, log1p
from typing import Any

from ..models.build import Build
from ..models.fields import Attack, AttackBucket, CalculatedStats
from ..models.upgrade import Upgrade
from ..utils.constants import DOT_MULTIPLIERS


class WeaponCalculator:
    def __init__(self, weapon: Any) -> None:
        self.weapon = weapon
        self.recompute()

    def _compute_base_stats(self, bucket: AttackBucket) -> None:
        attack = bucket.attack
        ammo, stats = self.weapon.data.entry.ammo, dict(attack.stats)
        stats.update({"attack_speed": attack.stats.fire_rate, "magazine_capacity": ammo.get("magazine_size", 1), "reload_speed": ammo.get("reload_time", 0), "recharge_rate": ammo.get("recharge_rate", 0)})
        bucket.base = CalculatedStats(self.weapon.mode_stats_type(stats).with_defaults())

    def _compute_modded_stats(self, bucket: AttackBucket) -> None:
        build, base, modded = bucket.build, bucket.base, bucket.modded
        damage = base.damage.apply(build.damage).combine().sorted()
        faction_damage = max(build.corpus_damage, build.grineer_damage, build.infested_damage, build.orokin_damage, build.murmur_damage, build.sentient_damage)

        modded.multiplicative_base_damage = max(1 + build.multiplicative_base_damage, 1)
        modded.base_damage = max(1 + build.base_damage, 0)
        modded.damage = modded.base_damage * damage
        modded.faction_damage = max(1 + faction_damage, 1)
        modded.flat_crit_chance = max(build.flat_crit_chance, 0)
        modded.multiplicative_crit_chance = max(1 + build.multiplicative_crit_chance, 1)
        modded.crit_chance = max(base.crit_chance * (1 + build.crit_chance), 0)
        modded.flat_crit_damage = max(build.flat_crit_damage, 0)
        modded.crit_damage = max(base.crit_damage * (1 + build.crit_damage), 1)
        modded.status_chance = max(base.status_chance * (1 + build.status_chance), 0)
        modded.status_damage = max(1 + build.status_damage, 1)

    def _compute_effective_stats(self, bucket: AttackBucket) -> None:
        base, modded, effective = bucket.base, bucket.modded, bucket.effective
        effective.forced_procs = base.forced_procs
        effective.base_damage = modded.base_damage * modded.multiplicative_base_damage
        effective.damage = modded.multiplicative_base_damage * modded.damage
        effective.faction_damage = modded.faction_damage
        effective.crit_chance = modded.crit_chance * modded.multiplicative_crit_chance + modded.flat_crit_chance
        effective.crit_damage = modded.crit_damage + modded.flat_crit_damage
        effective.status_chance = modded.status_chance
        effective.status_damage = modded.status_damage

    def _compute_average_stats(self, bucket: AttackBucket) -> None:
        effective, average = bucket.effective, bucket.average
        average.crit_chance = effective.crit_chance
        average.crit_multiplier = 1 + average.crit_chance * (effective.crit_damage - 1)

    def _average_condition_overload_bonus(self, bucket: AttackBucket) -> float:
        build, stats = bucket.build, bucket.attack.stats
        damage = stats.damage.apply(build.damage).combine().sorted()
        guaranteed, fractional = divmod(max(stats.status_chance * (1 + build.status_chance), 0), 1)
        guaranteed_hits, fractional_hit = divmod(max(self._status_hits(bucket), 0), 1)
        probabilities: dict[str, float] = {}
        for damage_type in damage.data:
            weight = damage.weight(damage_type)
            miss = (1 - weight) ** guaranteed * (1 - fractional * weight)
            probabilities[damage_type] = 1 - miss ** guaranteed_hits * (1 - fractional_hit + fractional_hit * miss)
        probabilities.update({damage_type: 1.0 for damage_type, count in stats.forced_procs if count > 0})

        condition_overload = build.condition_overload
        maximum = len(probabilities) if condition_overload.max_stacks == "inf" else int(condition_overload.max_stacks)
        attack_rate = self._effective_fire_rate(bucket)
        if maximum <= 0 or attack_rate <= 0:
            return 0.0
        attempts, distribution = attack_rate * 5, [1.0] + [0.0] * maximum
        for probability in probabilities.values():
            acquired = 0 if probability <= 0 else 1 if probability >= 1 else -expm1(attempts * log1p(-probability))
            updated = [0.0] * (maximum + 1)
            for count, chance in enumerate(distribution):
                updated[count] += chance * (1 - acquired)
                updated[min(count + 1, maximum)] += chance * acquired
            distribution = updated
        expected = sum(count * chance for count, chance in enumerate(distribution))
        return float(condition_overload.value) * stats.co_factor * expected

    def _status_hits(self, bucket: AttackBucket) -> float:
        build, stats, modded = bucket.build, bucket.attack.stats, bucket.modded
        hits = max(modded.get("multishot", stats.multishot), 1)
        duplicate = modded.get("melee_duplicate", 0)
        crit_chance = max(stats.crit_chance * (1 + build.crit_chance) * modded.multiplicative_crit_chance + modded.flat_crit_chance, 0)
        return hits + duplicate * max(0, 1 - abs(crit_chance - 1))

    def _effective_fire_rate(self, bucket: AttackBucket) -> float:
        stats, base, modded = bucket.attack.stats, bucket.base, bucket.modded
        if "attack_speed" in modded:
            return max(stats.fire_rate * modded.attack_speed / (base.attack_speed or 1), 0)
        if "magazine_capacity" not in modded:
            return max(stats.fire_rate, 0)

        build = bucket.build
        speed = 1 if build.fire_rate_lock else max(1 + build.fire_rate, 0.01)
        fire_rate = max(stats.fire_rate * speed, 0.05) * modded.multiplicative_fire_rate
        burst_count = max(stats.burst_count, 1)
        bursts = modded.magazine_capacity / burst_count
        is_battery = "recharge_delay" in self.weapon.data.entry.ammo
        is_beam = bucket.attack.delivery == "beam"
        reload_speed = modded.reload_speed + (0 if not is_battery else float("inf") if modded.recharge_rate <= 0 else modded.magazine_capacity / modded.recharge_rate)
        ammo_efficiency = 1 - (1 - modded.ammo_efficiency) / (2 if is_beam else 1)
        ammo_spent = 1 - ammo_efficiency
        cycle = bursts * (max(stats.charge_time, 0) / speed / modded.multiplicative_fire_rate + (burst_count - 1) * max(stats.burst_delay, 0) / max(speed, 1))
        cycle += (bursts - ammo_spent) / fire_rate + ammo_spent * reload_speed
        return float("inf") if cycle <= 0 else modded.magazine_capacity / cycle

    def _flat_dotph(self, bucket: AttackBucket, *, weakpoint: bool = False) -> float:
        base, effective, average = bucket.base, bucket.effective, bucket.average
        if effective.damage.total_damage() <= 0:
            return 0.0
        crit_multiplier = average.weakpoint_crit_multiplier if weakpoint else average.crit_multiplier
        regular = sum(multiplier * effective.damage.get(damage_type) * effective.damage.weight(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS) * effective.status_chance
        forced = sum(multiplier * base.forced_procs.get(damage_type) * effective.damage.get(damage_type) for damage_type, multiplier in DOT_MULTIPLIERS)
        hits = effective.get("multishot", self._status_hits(bucket)) * average.get("beam_dot_multiplier", 1)
        return (regular + forced) * effective.status_damage * effective.faction_damage ** 2 * crit_multiplier * hits

    def _compute_attack(self, name: str, attack: Attack, ancestors: frozenset[str] | None = None) -> AttackBucket:
        ancestors = frozenset() if ancestors is None else ancestors
        if name in ancestors:
            raise ValueError(f"cyclic attack relationship detected: {name}")

        evolutions = (Upgrade({f"{tier} perk {perk}": {"type": "evolution", "max_rank": 0, "compatibility": {"types": []}, "stats": self.weapon.data.entry.evolutions[tier.removeprefix("evolution_")][str(perk)].get("stats", {})}}) for tier, perk in self.weapon.evolutions.items())
        build = Build(*self.weapon.build, *evolutions)
        entry = self.weapon.data.entry
        build.stats.resolve({"context": {"name": self.weapon.data.name, "type": entry.type, "subtype": entry.subtype, "trigger": attack.trigger, "projectile": attack.delivery, "aoe": attack.aoe}})

        bucket = AttackBucket(attack=attack, build=build.stats.total.copy())
        self._compute_base_stats(bucket)
        self._compute_modded_stats(bucket)

        bonus = self._average_condition_overload_bonus(bucket)
        if bucket.attack.stats.co_effect == "multiplies":
            bucket.modded.multiplicative_base_damage = max(bucket.modded.multiplicative_base_damage + bonus, 1)
        else:
            bucket.modded.base_damage = max(bucket.modded.base_damage + bonus, 0)
        damage = bucket.base.damage.apply(bucket.build.damage).combine().sorted()
        bucket.modded.damage = bucket.modded.base_damage * damage

        self._compute_effective_stats(bucket)
        self._compute_average_stats(bucket)

        attacks = self.weapon.data.entry.attacks
        next_ancestors = ancestors | {name}
        bucket.children = [self._compute_attack(child, attacks[child], next_ancestors) for child in bucket.attack.children if child in attacks]
        return bucket

    def recompute(self) -> None:
        name = next(name for name, attack in self.weapon.data.entry.attacks.items() if attack is self.weapon.mode)
        self.parent = self._compute_attack(name, self.weapon.mode)
        self.child = self.parent.children

        def attacks(bucket: AttackBucket):
            yield bucket
            for child in bucket.children:
                yield from attacks(child)

        buckets = list(attacks(self.parent))
        combined = self.parent.average.copy()
        combined.flat_dph = sum(bucket.average.get("flat_dph", 0) for bucket in buckets)
        combined.flat_dotph = sum(bucket.average.get("flat_dotph", 0) for bucket in buckets)
        combined.total_dph = combined.flat_dph + combined.flat_dotph

        attack_rate = self._effective_fire_rate(self.parent)
        combined.flat_dps = combined.flat_dph * attack_rate
        combined.flat_dotps = combined.flat_dotph * attack_rate
        combined.total_dps = combined.total_dph * attack_rate

        if any("flat_weakpoint_dph" in bucket.average for bucket in buckets):
            combined.flat_weakpoint_dph = sum(bucket.average.get("flat_weakpoint_dph", 0) for bucket in buckets)
            combined.flat_weakpoint_dotph = sum(bucket.average.get("flat_weakpoint_dotph", 0) for bucket in buckets)
            combined.total_weakpoint_dph = combined.flat_weakpoint_dph + combined.flat_weakpoint_dotph
            combined.flat_weakpoint_dps = combined.flat_weakpoint_dph * attack_rate
            combined.flat_weakpoint_dotps = combined.flat_weakpoint_dotph * attack_rate
            combined.total_weakpoint_dps = combined.total_weakpoint_dph * attack_rate
        self.average = combined

    def contribution(self, upgrade: Upgrade) -> float:
        full = self.weapon.build
        if all(equipped.data != upgrade.data for equipped in full):
            return 0.0
        reduced = full - upgrade
        full_dps = self.average.total_dps
        try:
            self.weapon.configure(reduced)
            return full_dps - self.average.total_dps
        finally:
            self.weapon.configure(full)

    def contribution_values(self) -> dict[str, float]:
        return {str(upgrade.data.name): self.contribution(upgrade) for upgrade in self.weapon.build}

    def contribution_proportions(self) -> dict[str, float]:
        contributions = self.contribution_values()
        total = sum(contributions.values()) or 1
        return {name: contribution / total for name, contribution in contributions.items()}
