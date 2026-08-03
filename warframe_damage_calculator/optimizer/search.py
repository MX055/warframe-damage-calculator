from __future__ import annotations

import random

from ..domain.damage import BASE_ELEMENT_TYPES
from ..domain.generated_attacks import GENERATED_ATTACK_STAT
from ..domain.builds import Build
from ..domain.perks import Perk
from ..domain.upgrades import Arcane, Mod
from .candidates import Candidate


class Search:
    def _neighbors(self, build: Build, pools: dict[str, tuple], rng: random.Random):
        fixed = self.calculator.build
        mod_slots = 8 + (1 if any(mod.slot == "exilus_mod" for mod in pools["mods"]) else 0) + (1 if self.calculator.weapon.type == "melee" and any(mod.slot == "stance_mod" for mod in pools["mods"]) else 0)
        arcane_slots = 1
        if len(build.mods) < mod_slots:
            selected = {mod.name for mod in build.mods}
            for mod in self._shortlist(pools["mods"], selected, 36):
                candidate = self._build(mods=[*build.mods, mod], arcanes=build.arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
                if self._legal(candidate): yield candidate
        if len(build.arcanes) < arcane_slots:
            selected = {arcane.name for arcane in build.arcanes}
            for arcane in self._shortlist(pools["arcanes"], selected, 24):
                candidate = self._build(mods=build.mods, arcanes=[*build.arcanes, arcane], evolutions=build.evolutions, progenitor=build.progenitor)
                if self._legal(candidate): yield candidate
        fixed_mods = len(fixed.mods)
        for index in range(fixed_mods, len(build.mods)):
            selected = {mod.name for i, mod in enumerate(build.mods) if i != index}
            for mod in self._shortlist(pools["mods"], selected, 12):
                mods = list(build.mods)
                mods[index] = mod
                candidate = self._build(mods=mods, arcanes=build.arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
                if self._legal(candidate): yield candidate
        occupied = {self.calculator.weapon.perks[perk].tier for perk in build.evolutions if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier in occupied: continue
            for perk in choices: yield self._build(mods=build.mods, arcanes=build.arcanes, evolutions=[*build.evolutions, perk], progenitor=build.progenitor)
        if fixed.progenitor is None:
            for progenitor in pools["progenitors"]:
                if progenitor != build.progenitor: yield self._build(mods=build.mods, arcanes=build.arcanes, evolutions=build.evolutions, progenitor=progenitor)
        if len(build.mods) >= mod_slots and len(build.mods) > fixed_mods:
            indices = list(range(fixed_mods, len(build.mods)))
            rng.shuffle(indices)
            for index in indices[:4]:
                mods = list(build.mods)
                mods.pop(index)
                yield self._build(mods=mods, arcanes=build.arcanes, evolutions=build.evolutions, progenitor=build.progenitor)


    def _seed_builds(self, base: Build, pools: dict[str, tuple], *, search_scale: float = 1.0):
        profiles = (
            {"damage_bonus", "base_damage", "multiplicative_base_damage", "multishot"},
            {"crit_chance", "flat_crit_chance", "multiplicative_crit_chance", "crit_damage", "flat_crit_damage"},
            {"status_chance", "status_damage", "multishot"},
            {"fire_rate", "multiplicative_fire_rate", "attack_speed", "reload_speed", "magazine_capacity"},
            {"multishot", "crit_chance", "crit_damage"},
            {"multishot", "status_chance", "status_damage"},
            {"damage_bonus", "base_damage", "heat", "cold", "electricity", "toxin"},
            {"crit_chance", "crit_damage", "heat", "cold", "electricity", "toxin"},
            {"status_chance", "status_damage", "heat", "cold", "electricity", "toxin"},
            set(),
        )
        profiles = (*profiles,
                {"damage_bonus", "multishot", "crit_chance", "crit_damage", "status_chance", "status_damage"},
                {"multishot", "fire_rate", "reload_speed", "magazine_capacity"},
                {"damage_bonus", "multishot", "heat", "cold", "electricity", "toxin"},
                {"crit_chance", "crit_damage", "status_chance", "status_damage"},
                {"weak_point_damage", "weak_point_crit_chance", "crit_chance", "crit_damage"},
                {"damage_bonus", "weak_point_damage", "weak_point_crit_chance", "slash_proc", "status_chance", "status_damage", "status_duration", "cold", "toxin", "fire_rate"},
            )
        perk_limit = min(128, max(8, round(64 * search_scale ** 0.5)))
        perk_sets = self._perk_sets(base, pools, perk_limit)
        progenitors = (base.progenitor,) if base.progenitor is not None else (pools["progenitors"] or (None,))
        arcane_seed_limit = min(len(pools["arcanes"]), max(4, round(48 * search_scale ** 0.5)))
        arcanes = tuple(base.arcanes) if base.arcanes else (None, *pools["arcanes"][:arcane_seed_limit])
        seen: set[tuple] = set()
        for generator in (*pools["mods"], *pools["arcanes"]):
            dependencies = self._generated_attack_status_dependencies(generator)
            if not dependencies: continue
            allowed_mods = tuple(mod for mod in pools["mods"] if not ((set(mod.stats) & BASE_ELEMENT_TYPES) - dependencies) and not self._zeroes_base_damage(mod))
            seed_base = base
            arcanes_value = list(base.arcanes)
            if isinstance(generator, Mod):
                if generator.name in {mod.name for mod in base.mods}: continue
                seed_base = self._build(mods=[*base.mods, generator], arcanes=base.arcanes, evolutions=base.evolutions, progenitor=base.progenitor)
                if not self._legal(seed_base): continue
            else:
                if base.arcanes: continue
                arcanes_value = [generator]
            mods = self._profile_mods(seed_base, allowed_mods, {"damage_bonus", "base_damage", "crit_chance", "crit_damage", "status_chance", "status_damage", *dependencies})
            candidate = self._build(mods=mods, arcanes=arcanes_value, evolutions=base.evolutions, progenitor=base.progenitor)
            key = self._build_key(candidate)
            if key not in seen and self._legal(candidate):
                seen.add(key)
                yield candidate
        for profile in profiles:
            mods = self._profile_mods(base, pools["mods"], profile)
            profile_perk_limit = min(len(perk_sets), max(2, round(8 * search_scale ** 0.35)))
            for perks in perk_sets[:profile_perk_limit]:
                for progenitor in progenitors:
                    profile_arcane_limit = min(len(arcanes), max(2, round(16 * search_scale ** 0.35)))
                    for arcane in arcanes[:profile_arcane_limit]:
                        arcanes_value = list(base.arcanes) if base.arcanes else ([] if arcane is None else [arcane])
                        candidate = self._build(mods=mods, arcanes=arcanes_value, evolutions=perks, progenitor=progenitor)
                        key = self._build_key(candidate)
                        if key not in seen and self._legal(candidate):
                            seen.add(key)
                            yield candidate
        if not any(self._is_riven(mod) for mod in base.mods):
            riven_seed_limit = min(len(pools.get("rivens", ())), max(4, round(32 * search_scale ** 0.5)))
            for riven in pools.get("rivens", ())[:riven_seed_limit]:
                mods = self._profile_mods(base, tuple(mod for mod in pools["mods"] if not self._is_riven(mod)), set())
                regular_indices = [index for index, mod in enumerate(mods) if mod.slot == "regular_mod" and index >= len(base.mods)]
                if regular_indices:
                    mods[regular_indices[-1]] = riven
                elif sum(mod.slot == "regular_mod" for mod in mods) < 8:
                    mods.append(riven)
                candidate = self._build(mods=mods, arcanes=base.arcanes, evolutions=base.evolutions, progenitor=base.progenitor)
                key = self._build_key(candidate)
                if key not in seen and self._legal(candidate):
                    seen.add(key)
                    yield candidate
        for perks in perk_sets:
            candidate = self._build(mods=self._profile_mods(base, pools["mods"], set()), arcanes=base.arcanes, evolutions=perks, progenitor=base.progenitor)
            key = self._build_key(candidate)
            if key not in seen and self._legal(candidate):
                seen.add(key)
                yield candidate

    def _profile_mods(self, base: Build, pool: tuple, profile: set[str]) -> list[Mod]:
        mods = list(base.mods)
        selected = {mod.name for mod in mods}
        ranked = sorted((mod for mod in pool if mod.name not in selected), key=lambda mod: self._profile_priority(mod, profile), reverse=True)
        limits = {"regular_mod": 8, "exilus_mod": 1, "stance_mod": 1}
        counts: dict[str, int] = {}
        for mod in mods: counts[mod.slot] = counts.get(mod.slot, 0) + 1
        for mod in ranked:
            limit = limits.get(mod.slot, 0)
            if counts.get(mod.slot, 0) >= limit: continue
            trial = self._build(mods=[*mods, mod], arcanes=base.arcanes, evolutions=base.evolutions, progenitor=base.progenitor)
            if not self._legal(trial): continue
            mods.append(mod)
            selected.add(mod.name)
            counts[mod.slot] = counts.get(mod.slot, 0) + 1
        return mods

    @staticmethod
    def _generated_attack_status_dependencies(upgrade: Mod | Arcane) -> set[str]:
        dependencies: set[str] = set()
        for effect in upgrade.stats.get(GENERATED_ATTACK_STAT, ()):
            if effect.automatic.get("on") != "status_proc": continue
            conditions = effect.automatic.get("when", ())
            values = conditions if isinstance(conditions, list) else (conditions,)
            dependencies.update(str(value).removesuffix("_status_proc") for value in values if str(value).endswith("_status_proc"))
        return dependencies & BASE_ELEMENT_TYPES

    @staticmethod
    def _zeroes_base_damage(mod: Mod) -> bool:
        return any(isinstance(effect.value, (int, float)) and not isinstance(effect.value, bool) and effect.value <= -1 and not effect.automatic for stat in {"damage_bonus", "base_damage", "multiplicative_base_damage"} for effect in mod.stats.get(stat, ()))

    def _profile_priority(self, upgrade: Mod | Arcane, profile: set[str]) -> tuple[float, float, int, str]:
        matched = len(set(upgrade.stats) & profile)
        priority, stat_count, name = self._upgrade_priority(upgrade)
        return matched * 100.0 + priority, priority, stat_count, name

    def _perk_sets(self, base: Build, pools: dict[str, tuple], limit: int) -> list[list[Perk]]:
        sets = [list(base.evolutions)]
        fixed_tiers = {self.calculator.weapon.perks[perk].tier for perk in base.evolutions if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier in fixed_tiers: continue
            expanded = []
            for current in sets:
                for perk in choices: expanded.append([*current, perk])
            sets = expanded[:limit] or sets
        return sets[:limit]

    def _exact_neighbors(self, build: Build, pools: dict[str, tuple]):
        fixed = self.calculator.build
        seen: set[tuple] = set()
        for candidate in self._neighbors(build, pools, random.Random(0)):
            key = self._build_key(candidate)
            if key not in seen:
                seen.add(key)
                yield candidate
        for index in range(len(fixed.mods), len(build.mods)):
            selected = {mod.name for i, mod in enumerate(build.mods) if i != index}
            for mod in pools["mods"]:
                if mod.name in selected: continue
                mods = list(build.mods)
                mods[index] = mod
                candidate = self._build(mods=mods, arcanes=build.arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
                key = self._build_key(candidate)
                if key not in seen and self._legal(candidate):
                    seen.add(key)
                    yield candidate
        for index in range(len(fixed.arcanes), len(build.arcanes)):
            selected = {arcane.name for i, arcane in enumerate(build.arcanes) if i != index}
            for arcane in pools["arcanes"]:
                if arcane.name in selected: continue
                arcanes = list(build.arcanes)
                arcanes[index] = arcane
                candidate = self._build(mods=build.mods, arcanes=arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
                key = self._build_key(candidate)
                if key not in seen and self._legal(candidate):
                    seen.add(key)
                    yield candidate
        fixed_tiers = {self.calculator.weapon.perks[perk].tier for perk in fixed.evolutions if perk in self.calculator.weapon.perks}
        tier_indices = {self.calculator.weapon.perks[perk].tier: index for index, perk in enumerate(build.evolutions) if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier in fixed_tiers or tier not in tier_indices: continue
            index = tier_indices[tier]
            for perk in choices:
                if perk is build.evolutions[index]: continue
                evolutions = list(build.evolutions)
                evolutions[index] = perk
                candidate = self._build(mods=build.mods, arcanes=build.arcanes, evolutions=evolutions, progenitor=build.progenitor)
                key = self._build_key(candidate)
                if key not in seen:
                    seen.add(key)
                    yield candidate

    def _exact_perturbations(self, build: Build, pools: dict[str, tuple], *, search_scale: float = 1.0):
        fixed = self.calculator.build
        mutable = list(range(len(fixed.mods), len(build.mods)))
        ranked_limit = min(len(pools["mods"]), max(12, round(48 * search_scale ** 0.45)))
        ranked_mods = tuple(sorted(pools["mods"], key=self._upgrade_priority, reverse=True)[:ranked_limit])
        seen: set[tuple] = set()
        for left_pos in range(len(mutable)):
            for right_pos in range(left_pos + 1, len(mutable)):
                left = mutable[left_pos]
                right = mutable[right_pos]
                selected = {mod.name for index, mod in enumerate(build.mods) if index not in {left, right}}
                choices = [mod for mod in ranked_mods if mod.name not in selected]
                pair_limit = max(4, round(16 * search_scale ** 0.35))
                for first in choices[:pair_limit]:
                    for second in choices[:pair_limit]:
                        if first.name == second.name: continue
                        mods = list(build.mods)
                        mods[left], mods[right] = first, second
                        candidate = self._build(mods=mods, arcanes=build.arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
                        key = self._build_key(candidate)
                        if key not in seen and self._legal(candidate):
                            seen.add(key)
                            yield candidate
        if build.arcanes and len(build.mods) > len(fixed.mods):
            arcane_limit = min(len(pools["arcanes"]), max(8, round(48 * search_scale ** 0.4)))
            for arcane in pools["arcanes"][:arcane_limit]:
                for index in mutable:
                    selected = {mod.name for i, mod in enumerate(build.mods) if i != index}
                    mod_limit = min(len(ranked_mods), max(6, round(32 * search_scale ** 0.4)))
                    for mod in ranked_mods[:mod_limit]:
                        if mod.name in selected: continue
                        mods = list(build.mods)
                        mods[index] = mod
                        arcanes = list(build.arcanes)
                        arcanes[len(fixed.arcanes)] = arcane
                        candidate = self._build(mods=mods, arcanes=arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
                        key = self._build_key(candidate)
                        if key not in seen and self._legal(candidate):
                            seen.add(key)
                            yield candidate

    def _candidate_group(self, candidate: Candidate) -> tuple:
        build = candidate.build
        arcane = build.arcanes[0].name if build.arcanes else ""
        elements: set[str] = set()
        orientation: set[str] = set()
        for upgrade in build.ranked_upgrades:
            stats = set(upgrade.stats)
            elements.update(stats & {"heat", "cold", "electricity", "toxin", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "void"})
            if stats & {"crit_chance", "flat_crit_chance", "multiplicative_crit_chance", "crit_damage", "flat_crit_damage"}: orientation.add("crit")
            if stats & {"status_chance", "status_damage"}: orientation.add("status")
            if stats & {"multishot"}: orientation.add("multishot")
            if stats & {"fire_rate", "multiplicative_fire_rate", "attack_speed"}: orientation.add("speed")
        perks = tuple(sorted((self.calculator.weapon.perks[perk].tier, perk.name) for perk in build.evolutions if perk in self.calculator.weapon.perks))
        progenitor = None if build.progenitor is None else build.progenitor.element
        riven = next((self._riven_signature(mod) for mod in build.mods if self._is_riven(mod)), ())
        return arcane, tuple(sorted(elements)), tuple(sorted(orientation)), perks, progenitor, riven

    def _select_diverse(self, candidates: list[Candidate], limit: int) -> list[Candidate]:
        ordered = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
        unique: list[Candidate] = []
        seen_keys: set[tuple] = set()
        for candidate in ordered:
            key = self._build_key(candidate.build)
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append(candidate)
        global_limit = max(1, int(limit * 0.6))
        selected = unique[:global_limit]
        selected_keys = {self._build_key(candidate.build) for candidate in selected}
        seen_groups = {self._candidate_group(candidate) for candidate in selected}
        for candidate in unique[global_limit:]:
            if len(selected) >= limit: break
            group = self._candidate_group(candidate)
            key = self._build_key(candidate.build)
            if group not in seen_groups and key not in selected_keys:
                selected.append(candidate)
                selected_keys.add(key)
                seen_groups.add(group)
        for candidate in unique:
            if len(selected) >= limit: break
            key = self._build_key(candidate.build)
            if key not in selected_keys:
                selected.append(candidate)
                selected_keys.add(key)
        return selected

    def _perturbations(self, build: Build, pools: dict[str, tuple], rng: random.Random):
        fixed = self.calculator.build
        mutable_mods = list(range(len(fixed.mods), len(build.mods)))
        if len(mutable_mods) >= 2:
            pairs = [(mutable_mods[i], mutable_mods[j]) for i in range(len(mutable_mods)) for j in range(i + 1, len(mutable_mods))]
            rng.shuffle(pairs)
            for first, second in pairs[:8]:
                selected = {mod.name for index, mod in enumerate(build.mods) if index not in {first, second}}
                replacements = [mod for mod in pools["mods"] if mod.name not in selected]
                if len(replacements) < 2: continue
                for _ in range(2):
                    left, right = rng.sample(replacements, 2)
                    mods = list(build.mods)
                    mods[first], mods[second] = left, right
                    candidate = self._build(mods=mods, arcanes=build.arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
                    if self._legal(candidate): yield candidate
        if build.arcanes and len(build.mods) > len(fixed.mods):
            arcane_index = len(fixed.arcanes)
            if arcane_index < len(build.arcanes):
                mod_indices = list(range(len(fixed.mods), len(build.mods)))
                rng.shuffle(mod_indices)
                for mod_index in mod_indices[:4]:
                    for arcane in rng.sample(list(pools["arcanes"]), min(4, len(pools["arcanes"]))):
                        selected = {mod.name for index, mod in enumerate(build.mods) if index != mod_index}
                        choices = [mod for mod in pools["mods"] if mod.name not in selected]
                        if not choices: continue
                        mods = list(build.mods)
                        mods[mod_index] = rng.choice(choices)
                        arcanes = list(build.arcanes)
                        arcanes[arcane_index] = arcane
                        candidate = self._build(mods=mods, arcanes=arcanes, evolutions=build.evolutions, progenitor=build.progenitor)
                        if self._legal(candidate): yield candidate

    def _random_build(self, base: Build, pools: dict[str, tuple], rng: random.Random) -> Build:
        mods = list(base.mods)
        selected = {mod.name for mod in mods}
        for mod in rng.sample(list(pools["mods"]), min(max(0, 8 - len(mods)), len(pools["mods"]))):
            if mod.name not in selected:
                mods.append(mod)
                selected.add(mod.name)
        arcanes = list(base.arcanes)
        if not arcanes and pools["arcanes"]: arcanes.append(rng.choice(pools["arcanes"]))
        perks = list(base.evolutions)
        occupied = {self.calculator.weapon.perks[perk].tier for perk in perks if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier not in occupied: perks.append(rng.choice(choices))
        progenitor = base.progenitor or (rng.choice(pools["progenitors"]) if pools["progenitors"] else None)
        candidate = self._build(mods=mods, arcanes=arcanes, evolutions=perks, progenitor=progenitor)
        return candidate if self._legal(candidate) else base.copy()

    def _shortlist(self, pool: tuple, selected: set[str], limit: int) -> tuple:
        return tuple(upgrade for upgrade in pool if upgrade.name not in selected)[:limit]
