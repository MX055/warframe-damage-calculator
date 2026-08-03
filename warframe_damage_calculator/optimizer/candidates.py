from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from ..database.arsenal import arsenal
from ..domain.builds import Build, Progenitor
from ..domain.perks import Perk
from ..domain.results import CalculationResult
from ..domain.upgrades import Arcane, Mod, ResolvedEffect
from .rivens import DEFAULT_RIVEN_STAT_BLACKLIST, FACTION_DAMAGE_STATS


DEFAULT_UPGRADE_BLACKLIST = frozenset({
    "Aero Agility", "Aero Periphery", "Air Recon", "Akimbo Slip Shot", "Avenging Truth", "Broad Eye", "Cascadia Accuracy", "Cascadia Overcharge", "Catalyzer Link", "Combo Fury", "Combo Killer", "Deadly Maneuvers", "Dreadful Killshot", "Embedded Catalyzer", "Exodia Contagion", "Exodia Epidemic", "Fractalized Reset", "Hunter Synergy", "Mark of the Beast", "Mecha Overdrive", "Melee Assimilation", "Melee Careen", "Melee Exposure", "Melee Retaliation", "Mortal Conduct", "Nano-Applicator", "Necrophagic Vigor", "Overview", "Pax Soar", "Primary Bulwark", "Primary Dexterity", "Primary Overcharge", "Proton Jet", "Proton Snap", "Secondary Dexterity", "Secondary Kinship", "Secondary Outburst", "Secondary Surge", "Soaring Strike", "Spectral Serration", "Zazvat-Kar",
})


@dataclass(frozen=True, slots=True)
class Candidate:
    build: Build
    score: float
    result: CalculationResult | None = None


class CandidatePreparation:
    def _build(self, *, mods=(), arcanes=(), evolutions=(), progenitor=None) -> Build:
        return Build._from_parts(mods=mods, arcanes=arcanes, evolutions=evolutions, progenitor=progenitor)

    def _candidate_pools(self, *, riven: bool = True, evolutions: bool = True, upgrade_blacklist: Collection[str] | None = DEFAULT_UPGRADE_BLACKLIST, riven_stat_blacklist: Collection[str] | None = DEFAULT_RIVEN_STAT_BLACKLIST, search_scale: float = 1.0) -> dict[str, tuple]:
        use_default_upgrade_blacklist = upgrade_blacklist == DEFAULT_UPGRADE_BLACKLIST
        upgrade_blacklist = frozenset() if upgrade_blacklist is None else frozenset(name.casefold() for name in map(str, upgrade_blacklist))
        riven_stat_blacklist = frozenset() if riven_stat_blacklist is None else frozenset(map(str, riven_stat_blacklist))
        weapon = self.calculator.weapon
        compatible_mods = tuple(mod for mod in arsenal.mod.filter(weapon=weapon, implemented=True) if mod.name.casefold() not in upgrade_blacklist and not (use_default_upgrade_blacklist and self._has_faction_damage(mod)))
        mod_limit = min(192, max(36, round(108 * search_scale ** 0.4)))
        regular_mods = self._prepare_pool(compatible_mods, mod_limit)
        locked_riven = any(self._is_riven(mod) for mod in self.calculator.build.mods)
        riven_limit = min(192, max(16, round(64 * search_scale ** 0.5)))
        rivens = () if locked_riven or not riven else self._riven_candidates(limit=riven_limit, stat_blacklist=riven_stat_blacklist)
        mods = (*regular_mods, *rivens)
        compatible_arcanes = tuple(arcane for arcane in arsenal.arcane.filter(weapon=weapon, implemented=True) if arcane.name.casefold() not in upgrade_blacklist and not (use_default_upgrade_blacklist and self._has_faction_damage(arcane)))
        arcane_limit = min(96, max(18, round(54 * search_scale ** 0.4)))
        arcanes = self._prepare_pool(compatible_arcanes, arcane_limit)
        perks = {tier: implemented for tier, choices in weapon.perk_choices.items() if evolutions and (implemented := tuple(perk for perk in choices.values() if perk.implemented and perk.name.casefold() not in upgrade_blacklist and not (use_default_upgrade_blacklist and self._has_faction_damage(perk))))}
        progenitors = tuple(Progenitor(element=element, bonus=0.6) for element in ("impact", "heat", "cold", "electricity", "toxin", "magnetic", "radiation")) if "progenitor" in weapon.traits else ()
        return {"mods": mods, "arcanes": arcanes, "perks": perks, "progenitors": progenitors, "rivens": rivens}

    def _has_faction_damage(self, upgrade: Mod | Arcane | Perk) -> bool:
        return bool(FACTION_DAMAGE_STATS.intersection(upgrade.stats))

    def _prepare_pool(self, pool: tuple, limit: int) -> tuple:
        ranked = sorted(pool, key=self._upgrade_priority, reverse=True)
        selected: list = []
        seen: set[str] = set()
        per_stat: dict[str, int] = {}
        for upgrade in ranked:
            stats = tuple(upgrade.stats)
            if any(per_stat.get(stat, 0) < 3 for stat in stats) or len(selected) < limit // 2:
                selected.append(upgrade)
                seen.add(upgrade.name)
                for stat in stats: per_stat[stat] = per_stat.get(stat, 0) + 1
            if len(selected) >= limit: break
        if len(selected) < limit:
            selected.extend(upgrade for upgrade in ranked if upgrade.name not in seen)
        return tuple(selected[:limit])

    def _upgrade_priority(self, upgrade: Mod | Arcane) -> tuple[float, int, str]:
        runtime = tuple(sorted(upgrade.runtime.as_dict().items()))
        riven_stats = self._riven_signature(upgrade) if isinstance(upgrade, Mod) and self._is_riven(upgrade) else ()
        key = (type(upgrade), upgrade.name, upgrade.slot, runtime, riven_stats)
        cached = self._priority_cache.get(key)
        if cached is not None: return cached
        relevant = {"damage_bonus", "base_damage", "multiplicative_base_damage", "multishot", "crit_chance", "flat_crit_chance", "multiplicative_crit_chance", "crit_damage", "flat_crit_damage", "slide_crit_chance", "status_chance", "status_damage", "fire_rate", "multiplicative_fire_rate", "attack_speed", "weak_point_damage", "weak_point_crit_chance", "reload_speed", "magazine_capacity", "ammo_efficiency", "impact", "puncture", "slash", "cold", "electricity", "heat", "toxin", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "void"}
        score = 0.0
        special = 0
        for stat, effects in upgrade.stats.items():
            if stat in relevant: score += 1.0
            for effect in effects:
                if isinstance(effect.value, (int, float)) and not isinstance(effect.value, bool): score += min(abs(float(effect.value)), 10.0)
                if effect.automatic: special += 1
        priority = score + special * 4.0, len(upgrade.stats), upgrade.name
        self._priority_cache[key] = priority
        return priority

    def _estimate_build(self, build: Build) -> float:
        score = 0.0
        for upgrade in build.ranked_upgrades:
            priority, stat_count, _ = self._upgrade_priority(upgrade)
            score += priority + stat_count * 0.25
        score += len(build.evolutions) * 12.0
        if build.progenitor is not None: score += 8.0 + build.progenitor.bonus * 10.0
        names = {upgrade.name for upgrade in build.ranked_upgrades}
        elemental = sum(name in names for name in ("heat", "cold", "electricity", "toxin"))
        return score + elemental * 2.0

    def _open_slots(self, build: Build, pools: dict[str, tuple]) -> int:
        mod_slots = 8 + (1 if any(mod.slot == "exilus_mod" for mod in pools["mods"]) else 0) + (1 if self.calculator.weapon.type == "melee" and any(mod.slot == "stance_mod" for mod in pools["mods"]) else 0)
        occupied_tiers = {self.calculator.weapon.perks[perk].tier for perk in build.evolutions if perk in self.calculator.weapon.perks}
        return max(0, mod_slots - len(build.mods)) + max(0, 1 - len(build.arcanes)) + sum(tier not in occupied_tiers for tier in pools["perks"]) + int(build.progenitor is None and bool(pools["progenitors"]))

    def _complete_fixed_build(self, source: Build, *, evolutions: bool = True) -> Build:
        perks = list(source.evolutions)
        if evolutions:
            occupied = {self.calculator.weapon.perks[perk].tier for perk in perks if perk in self.calculator.weapon.perks}
            for tier, choices in self.calculator.weapon.perk_choices.items():
                implemented = tuple(perk for perk in choices.values() if perk.implemented)
                if tier not in occupied and len(implemented) == 1: perks.extend(implemented)
        return self._build(mods=source.mods, arcanes=source.arcanes, evolutions=perks, progenitor=source.progenitor)

    def _cleanup_removals(self, build: Build) -> list[tuple[int, Build]]:
        fixed = self.calculator.build
        removals: list[tuple[int, Build]] = []
        for index in range(len(fixed.mods), len(build.mods)):
            candidate = self._build(mods=[mod for i, mod in enumerate(build.mods) if i != index], arcanes=build.arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
            if self._legal(candidate): removals.append((index, candidate))
        offset = len(build.mods)
        for index in range(len(fixed.arcanes), len(build.arcanes)):
            candidate = self._build(mods=build.mods, arcanes=[arcane for i, arcane in enumerate(build.arcanes) if i != index], evolutions=build.evolutions, progenitor=build.progenitor)
            if self._legal(candidate): removals.append((offset + index, candidate))
        return removals

    def _cleanup_replacements(self, build: Build, pools: dict[str, tuple], weak_indices: list[int], *, limit: int) -> list[Build]:
        fixed = self.calculator.build
        fixed_tiers = {self.calculator.weapon.perks[perk].tier for perk in fixed.evolutions if perk in self.calculator.weapon.perks}
        candidates: dict[tuple, Build] = {}
        for encoded_index in weak_indices:
            if encoded_index < len(build.mods):
                index = encoded_index
                selected = {mod.name for i, mod in enumerate(build.mods) if i != index}
                ranked = sorted((mod for mod in pools["mods"] if mod.name not in selected), key=self._upgrade_priority, reverse=True)[:limit]
                for mod in ranked:
                    mods = list(build.mods)
                    mods[index] = mod
                    candidate = self._build(mods=mods, arcanes=build.arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
                    if self._legal(candidate): candidates.setdefault(self._build_key(candidate), candidate)
            else:
                index = encoded_index - len(build.mods)
                if index < len(fixed.arcanes): continue
                selected = {arcane.name for i, arcane in enumerate(build.arcanes) if i != index}
                ranked = sorted((arcane for arcane in pools["arcanes"] if arcane.name not in selected), key=self._upgrade_priority, reverse=True)[:limit]
                for arcane in ranked:
                    arcanes = list(build.arcanes)
                    arcanes[index] = arcane
                    candidate = self._build(mods=build.mods, arcanes=arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
                    if self._legal(candidate): candidates.setdefault(self._build_key(candidate), candidate)
        tier_indices = {self.calculator.weapon.perks[perk].tier: index for index, perk in enumerate(build.evolutions) if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier in fixed_tiers or tier not in tier_indices: continue
            index = tier_indices[tier]
            for perk in choices:
                if perk == build.evolutions[index]: continue
                evolutions = list(build.evolutions)
                evolutions[index] = perk
                candidate = self._build(mods=build.mods, arcanes=build.arcanes, evolutions=evolutions, progenitor=build.progenitor)
                candidates.setdefault(self._build_key(candidate), candidate)
        if fixed.progenitor is None:
            for progenitor in pools["progenitors"]:
                if progenitor == build.progenitor: continue
                candidate = self._build(mods=build.mods, arcanes=build.arcanes, evolutions=build.evolutions, progenitor=progenitor)
                candidates.setdefault(self._build_key(candidate), candidate)
        return sorted(candidates.values(), key=self._estimate_build, reverse=True)[:max(limit * max(1, len(weak_indices)), limit)]

    def _legal(self, build: Build) -> bool:
        if sum(self._is_riven(mod) for mod in build.mods) > 1: return False
        upgrades = list(build.ranked_upgrades)
        names = {upgrade.name for upgrade in upgrades}
        if len(names) != len(upgrades): return False
        for upgrade in upgrades:
            if any(conflict in names for conflict in upgrade.conflicts): return False
        slot_counts: dict[str, int] = {}
        for mod in build.mods: slot_counts[mod.slot] = slot_counts.get(mod.slot, 0) + 1
        if slot_counts.get("regular_mod", 0) > 8 or slot_counts.get("exilus_mod", 0) > 1 or slot_counts.get("stance_mod", 0) > 1: return False
        return True

    def _component_id(self, component: object) -> int:
        identity = id(component)
        cached = self._component_id_cache.get(identity)
        if cached is not None and cached[0] is component: return cached[1]
        assigned = self._next_component_id
        self._next_component_id += 1
        self._component_id_cache[identity] = component, assigned
        return assigned

    def _compiled_upgrade_effects(self, build: Build) -> tuple[ResolvedEffect, ...]:
        upgrades = build.ranked_upgrades
        key = tuple(self._component_id(upgrade) for upgrade in upgrades)
        cached = self._upgrade_effects_cache.get(key)
        if cached is not None: return cached
        groups: list[tuple[ResolvedEffect, ...]] = []
        for upgrade in upgrades:
            if not upgrade.implemented: continue
            component_id = self._component_id(upgrade)
            effects = self._resolved_effect_cache.get(component_id)
            if effects is None:
                effects = upgrade.resolve_manual()
                self._resolved_effect_cache[component_id] = effects
            groups.append(effects)
        compiled = tuple(effect for effects in groups for effect in effects)
        self._upgrade_effects_cache[key] = compiled
        return compiled

    def _build_key(self, build: Build) -> tuple:
        return (tuple(self._component_id(mod) for mod in build.mods), tuple(self._component_id(arcane) for arcane in build.arcanes), tuple(self._component_id(perk) for perk in build.evolutions), None if build.progenitor is None else (build.progenitor.element, build.progenitor.bonus))

