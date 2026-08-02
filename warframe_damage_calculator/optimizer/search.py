from __future__ import annotations

import random

from ..domain.damage import BASE_ELEMENT_TYPES
from ..domain.loadouts import Loadout
from ..domain.perks import Perk
from ..domain.upgrades import Arcane, Mod
from .candidates import Candidate


class Search:
    def _neighbors(self, loadout: Loadout, pools: dict[str, tuple], rng: random.Random):
        fixed = self.calculator.loadout
        mod_slots = 8 + (1 if any(mod.slot == "exilus_mod" for mod in pools["mods"]) else 0) + (1 if self.calculator.weapon.type == "melee" and any(mod.slot == "stance_mod" for mod in pools["mods"]) else 0)
        arcane_slots = 1
        if len(loadout.mods) < mod_slots:
            selected = {mod.name for mod in loadout.mods}
            for mod in self._shortlist(pools["mods"], selected, 36):
                candidate = self._loadout(mods=[*loadout.mods, mod], arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                if self._legal(candidate): yield candidate
        if len(loadout.arcanes) < arcane_slots:
            selected = {arcane.name for arcane in loadout.arcanes}
            for arcane in self._shortlist(pools["arcanes"], selected, 24):
                candidate = self._loadout(mods=loadout.mods, arcanes=[*loadout.arcanes, arcane], evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                if self._legal(candidate): yield candidate
        fixed_mods = len(fixed.mods)
        for index in range(fixed_mods, len(loadout.mods)):
            selected = {mod.name for i, mod in enumerate(loadout.mods) if i != index}
            for mod in self._shortlist(pools["mods"], selected, 12):
                mods = list(loadout.mods)
                mods[index] = mod
                candidate = self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                if self._legal(candidate): yield candidate
        occupied = {self.calculator.weapon.perks[perk].tier for perk in loadout.evolutions if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier in occupied: continue
            for perk in choices: yield self._loadout(mods=loadout.mods, arcanes=loadout.arcanes, evolutions=[*loadout.evolutions, perk], progenitor=loadout.progenitor)
        if fixed.progenitor is None:
            for progenitor in pools["progenitors"]:
                if progenitor != loadout.progenitor: yield self._loadout(mods=loadout.mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=progenitor)
        if len(loadout.mods) >= mod_slots and len(loadout.mods) > fixed_mods:
            indices = list(range(fixed_mods, len(loadout.mods)))
            rng.shuffle(indices)
            for index in indices[:4]:
                mods = list(loadout.mods)
                mods.pop(index)
                yield self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)


    def _seed_loadouts(self, base: Loadout, pools: dict[str, tuple], *, search_scale: float = 1.0):
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
                {"weakpoint_damage", "weakpoint_crit_chance", "crit_chance", "crit_damage"},
                {"damage_bonus", "weakpoint_damage", "weakpoint_crit_chance", "slash_proc", "status_chance", "status_damage", "status_duration", "cold", "toxin", "fire_rate"},
            )
        perk_limit = min(128, max(8, round(64 * search_scale ** 0.5)))
        perk_sets = self._perk_sets(base, pools, perk_limit)
        progenitors = (base.progenitor,) if base.progenitor is not None else (pools["progenitors"] or (None,))
        arcane_seed_limit = min(len(pools["arcanes"]), max(4, round(48 * search_scale ** 0.5)))
        arcanes = tuple(base.arcanes) if base.arcanes else (None, *pools["arcanes"][:arcane_seed_limit])
        seen: set[tuple] = set()
        for generator in (*pools["mods"], *pools["arcanes"]):
            dependencies = self._extra_attack_status_dependencies(generator)
            if not dependencies: continue
            allowed_mods = tuple(mod for mod in pools["mods"] if not ((set(mod.stats) & BASE_ELEMENT_TYPES) - dependencies) and not self._zeroes_base_damage(mod))
            seed_base = base
            arcanes_value = list(base.arcanes)
            if isinstance(generator, Mod):
                if generator.name in {mod.name for mod in base.mods}: continue
                seed_base = self._loadout(mods=[*base.mods, generator], arcanes=base.arcanes, evolutions=base.evolutions, progenitor=base.progenitor)
                if not self._legal(seed_base): continue
            else:
                if base.arcanes: continue
                arcanes_value = [generator]
            mods = self._profile_mods(seed_base, allowed_mods, {"damage_bonus", "base_damage", "crit_chance", "crit_damage", "status_chance", "status_damage", *dependencies})
            candidate = self._loadout(mods=mods, arcanes=arcanes_value, evolutions=base.evolutions, progenitor=base.progenitor)
            key = self._loadout_key(candidate)
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
                        candidate = self._loadout(mods=mods, arcanes=arcanes_value, evolutions=perks, progenitor=progenitor)
                        key = self._loadout_key(candidate)
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
                candidate = self._loadout(mods=mods, arcanes=base.arcanes, evolutions=base.evolutions, progenitor=base.progenitor)
                key = self._loadout_key(candidate)
                if key not in seen and self._legal(candidate):
                    seen.add(key)
                    yield candidate
        for perks in perk_sets:
            candidate = self._loadout(mods=self._profile_mods(base, pools["mods"], set()), arcanes=base.arcanes, evolutions=perks, progenitor=base.progenitor)
            key = self._loadout_key(candidate)
            if key not in seen and self._legal(candidate):
                seen.add(key)
                yield candidate

    def _profile_mods(self, base: Loadout, pool: tuple, profile: set[str]) -> list[Mod]:
        mods = list(base.mods)
        selected = {mod.name for mod in mods}
        ranked = sorted((mod for mod in pool if mod.name not in selected), key=lambda mod: self._profile_priority(mod, profile), reverse=True)
        limits = {"regular_mod": 8, "exilus_mod": 1, "stance_mod": 1}
        counts: dict[str, int] = {}
        for mod in mods: counts[mod.slot] = counts.get(mod.slot, 0) + 1
        for mod in ranked:
            limit = limits.get(mod.slot, 0)
            if counts.get(mod.slot, 0) >= limit: continue
            trial = self._loadout(mods=[*mods, mod], arcanes=base.arcanes, evolutions=base.evolutions, progenitor=base.progenitor)
            if not self._legal(trial): continue
            mods.append(mod)
            selected.add(mod.name)
            counts[mod.slot] = counts.get(mod.slot, 0) + 1
        return mods

    @staticmethod
    def _extra_attack_status_dependencies(upgrade: Mod | Arcane) -> set[str]:
        dependencies: set[str] = set()
        for effect in upgrade.stats.get("extra_attack", ()):
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

    def _perk_sets(self, base: Loadout, pools: dict[str, tuple], limit: int) -> list[list[Perk]]:
        sets = [list(base.evolutions)]
        fixed_tiers = {self.calculator.weapon.perks[perk].tier for perk in base.evolutions if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier in fixed_tiers: continue
            expanded = []
            for current in sets:
                for perk in choices: expanded.append([*current, perk])
            sets = expanded[:limit] or sets
        return sets[:limit]

    def _exact_neighbors(self, loadout: Loadout, pools: dict[str, tuple]):
        fixed = self.calculator.loadout
        seen: set[tuple] = set()
        for candidate in self._neighbors(loadout, pools, random.Random(0)):
            key = self._loadout_key(candidate)
            if key not in seen:
                seen.add(key)
                yield candidate
        for index in range(len(fixed.mods), len(loadout.mods)):
            selected = {mod.name for i, mod in enumerate(loadout.mods) if i != index}
            for mod in pools["mods"]:
                if mod.name in selected: continue
                mods = list(loadout.mods)
                mods[index] = mod
                candidate = self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                key = self._loadout_key(candidate)
                if key not in seen and self._legal(candidate):
                    seen.add(key)
                    yield candidate
        for index in range(len(fixed.arcanes), len(loadout.arcanes)):
            selected = {arcane.name for i, arcane in enumerate(loadout.arcanes) if i != index}
            for arcane in pools["arcanes"]:
                if arcane.name in selected: continue
                arcanes = list(loadout.arcanes)
                arcanes[index] = arcane
                candidate = self._loadout(mods=loadout.mods, arcanes=arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                key = self._loadout_key(candidate)
                if key not in seen and self._legal(candidate):
                    seen.add(key)
                    yield candidate
        fixed_tiers = {self.calculator.weapon.perks[perk].tier for perk in fixed.evolutions if perk in self.calculator.weapon.perks}
        tier_indices = {self.calculator.weapon.perks[perk].tier: index for index, perk in enumerate(loadout.evolutions) if perk in self.calculator.weapon.perks}
        for tier, choices in pools["perks"].items():
            if tier in fixed_tiers or tier not in tier_indices: continue
            index = tier_indices[tier]
            for perk in choices:
                if perk is loadout.evolutions[index]: continue
                evolutions = list(loadout.evolutions)
                evolutions[index] = perk
                candidate = self._loadout(mods=loadout.mods, arcanes=loadout.arcanes, evolutions=evolutions, progenitor=loadout.progenitor)
                key = self._loadout_key(candidate)
                if key not in seen:
                    seen.add(key)
                    yield candidate

    def _exact_perturbations(self, loadout: Loadout, pools: dict[str, tuple], *, search_scale: float = 1.0):
        fixed = self.calculator.loadout
        mutable = list(range(len(fixed.mods), len(loadout.mods)))
        ranked_limit = min(len(pools["mods"]), max(12, round(48 * search_scale ** 0.45)))
        ranked_mods = tuple(sorted(pools["mods"], key=self._upgrade_priority, reverse=True)[:ranked_limit])
        seen: set[tuple] = set()
        for left_pos in range(len(mutable)):
            for right_pos in range(left_pos + 1, len(mutable)):
                left = mutable[left_pos]
                right = mutable[right_pos]
                selected = {mod.name for index, mod in enumerate(loadout.mods) if index not in {left, right}}
                choices = [mod for mod in ranked_mods if mod.name not in selected]
                pair_limit = max(4, round(16 * search_scale ** 0.35))
                for first in choices[:pair_limit]:
                    for second in choices[:pair_limit]:
                        if first.name == second.name: continue
                        mods = list(loadout.mods)
                        mods[left], mods[right] = first, second
                        candidate = self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                        key = self._loadout_key(candidate)
                        if key not in seen and self._legal(candidate):
                            seen.add(key)
                            yield candidate
        if loadout.arcanes and len(loadout.mods) > len(fixed.mods):
            arcane_limit = min(len(pools["arcanes"]), max(8, round(48 * search_scale ** 0.4)))
            for arcane in pools["arcanes"][:arcane_limit]:
                for index in mutable:
                    selected = {mod.name for i, mod in enumerate(loadout.mods) if i != index}
                    mod_limit = min(len(ranked_mods), max(6, round(32 * search_scale ** 0.4)))
                    for mod in ranked_mods[:mod_limit]:
                        if mod.name in selected: continue
                        mods = list(loadout.mods)
                        mods[index] = mod
                        arcanes = list(loadout.arcanes)
                        arcanes[len(fixed.arcanes)] = arcane
                        candidate = self._loadout(mods=mods, arcanes=arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                        key = self._loadout_key(candidate)
                        if key not in seen and self._legal(candidate):
                            seen.add(key)
                            yield candidate

    def _candidate_group(self, candidate: Candidate) -> tuple:
        loadout = candidate.loadout
        arcane = loadout.arcanes[0].name if loadout.arcanes else ""
        elements: set[str] = set()
        orientation: set[str] = set()
        for upgrade in loadout.ranked_upgrades:
            stats = set(upgrade.stats)
            elements.update(stats & {"heat", "cold", "electricity", "toxin", "blast", "corrosive", "gas", "magnetic", "radiation", "viral", "void"})
            if stats & {"crit_chance", "flat_crit_chance", "multiplicative_crit_chance", "crit_damage", "flat_crit_damage"}: orientation.add("crit")
            if stats & {"status_chance", "status_damage"}: orientation.add("status")
            if stats & {"multishot"}: orientation.add("multishot")
            if stats & {"fire_rate", "multiplicative_fire_rate", "attack_speed"}: orientation.add("speed")
        perks = tuple(sorted((self.calculator.weapon.perks[perk].tier, perk.name) for perk in loadout.evolutions if perk in self.calculator.weapon.perks))
        progenitor = None if loadout.progenitor is None else loadout.progenitor.element
        riven = next((self._riven_signature(mod) for mod in loadout.mods if self._is_riven(mod)), ())
        return arcane, tuple(sorted(elements)), tuple(sorted(orientation)), perks, progenitor, riven

    def _select_diverse(self, candidates: list[Candidate], limit: int) -> list[Candidate]:
        ordered = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
        unique: list[Candidate] = []
        seen_keys: set[tuple] = set()
        for candidate in ordered:
            key = self._loadout_key(candidate.loadout)
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append(candidate)
        global_limit = max(1, int(limit * 0.6))
        selected = unique[:global_limit]
        selected_keys = {self._loadout_key(candidate.loadout) for candidate in selected}
        seen_groups = {self._candidate_group(candidate) for candidate in selected}
        for candidate in unique[global_limit:]:
            if len(selected) >= limit: break
            group = self._candidate_group(candidate)
            key = self._loadout_key(candidate.loadout)
            if group not in seen_groups and key not in selected_keys:
                selected.append(candidate)
                selected_keys.add(key)
                seen_groups.add(group)
        for candidate in unique:
            if len(selected) >= limit: break
            key = self._loadout_key(candidate.loadout)
            if key not in selected_keys:
                selected.append(candidate)
                selected_keys.add(key)
        return selected

    def _perturbations(self, loadout: Loadout, pools: dict[str, tuple], rng: random.Random):
        fixed = self.calculator.loadout
        mutable_mods = list(range(len(fixed.mods), len(loadout.mods)))
        if len(mutable_mods) >= 2:
            pairs = [(mutable_mods[i], mutable_mods[j]) for i in range(len(mutable_mods)) for j in range(i + 1, len(mutable_mods))]
            rng.shuffle(pairs)
            for first, second in pairs[:8]:
                selected = {mod.name for index, mod in enumerate(loadout.mods) if index not in {first, second}}
                replacements = [mod for mod in pools["mods"] if mod.name not in selected]
                if len(replacements) < 2: continue
                for _ in range(2):
                    left, right = rng.sample(replacements, 2)
                    mods = list(loadout.mods)
                    mods[first], mods[second] = left, right
                    candidate = self._loadout(mods=mods, arcanes=loadout.arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                    if self._legal(candidate): yield candidate
        if loadout.arcanes and len(loadout.mods) > len(fixed.mods):
            arcane_index = len(fixed.arcanes)
            if arcane_index < len(loadout.arcanes):
                mod_indices = list(range(len(fixed.mods), len(loadout.mods)))
                rng.shuffle(mod_indices)
                for mod_index in mod_indices[:4]:
                    for arcane in rng.sample(list(pools["arcanes"]), min(4, len(pools["arcanes"]))):
                        selected = {mod.name for index, mod in enumerate(loadout.mods) if index != mod_index}
                        choices = [mod for mod in pools["mods"] if mod.name not in selected]
                        if not choices: continue
                        mods = list(loadout.mods)
                        mods[mod_index] = rng.choice(choices)
                        arcanes = list(loadout.arcanes)
                        arcanes[arcane_index] = arcane
                        candidate = self._loadout(mods=mods, arcanes=arcanes, evolutions=loadout.evolutions, progenitor=loadout.progenitor)
                        if self._legal(candidate): yield candidate

    def _random_loadout(self, base: Loadout, pools: dict[str, tuple], rng: random.Random) -> Loadout:
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
        candidate = self._loadout(mods=mods, arcanes=arcanes, evolutions=perks, progenitor=progenitor)
        return candidate if self._legal(candidate) else base.copy()

    def _shortlist(self, pool: tuple, selected: set[str], limit: int) -> tuple:
        return tuple(upgrade for upgrade in pool if upgrade.name not in selected)[:limit]
