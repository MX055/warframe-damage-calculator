from __future__ import annotations

from dataclasses import replace

from ..models import Build, Upgrade
from ..models.dist import dist
from ..states import WeaponState
from ..utils import DAMAGE_TYPES, Value


class UpgradeResolver:
    AUTOMATIC_CONDITIONS = {"primary", "rifle", "bow", "shotgun", "sniper", "secondary", "pistol", "melee", "sacrificial set"}

    @staticmethod
    def _key(value: str) -> str:
        return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())

    def _weapon_context(self, weapon: WeaponState) -> set[str]:
        weapon_type = self._key(str(weapon.type or ""))
        context = {weapon_type}
        if weapon_type in {"rifle", "bow", "shotgun", "sniper"}:
            context.add("primary")
        if weapon_type == "bow":
            context.add("rifle")
        if weapon_type == "pistol":
            context.add("secondary")
        return context

    def _resolve_context(self, upgrade: Upgrade, weapon: WeaponState, build: Build) -> dict[str, object]:
        context = {self._key(key): value for key, value in upgrade.context.items()}
        weapon_context = self._weapon_context(weapon)
        context.update({condition: True for condition in weapon_context})
        context["weapon"] = self._key(str(weapon.type or ""))
        names = {self._key(item.name or "") for item in build}
        context["sacrificial set"] = {"sacrificial pressure", "sacrificial steel"}.issubset(names)
        context.setdefault("rank", upgrade.max_rank or 0)
        return context

    def _condition_active(self, condition: str, context: dict[str, object], use_defaults: bool) -> bool:
        condition = self._key(condition)
        default = False if condition in self.AUTOMATIC_CONDITIONS else use_defaults
        return bool(context.get(condition, default))

    @staticmethod
    def _scale(value: Value, multiplier: float) -> Value:
        return value if isinstance(value, bool) else value * multiplier

    @staticmethod
    def _merge(target: dict[str, Value], stat: str, value: Value) -> None:
        if stat in DAMAGE_TYPES:
            value = dist(**{stat: value})
            stat = "damage_dist"
        current = target.get(stat)
        if current is None:
            target[stat] = value
        elif isinstance(current, bool) and isinstance(value, bool):
            target[stat] = current or value
        elif isinstance(current, dist) and isinstance(value, dist):
            target[stat] = current + value
        elif isinstance(current, (int, float)) and isinstance(value, (int, float)):
            target[stat] = current + value
        else:
            raise TypeError

    def resolve(self, weapon: WeaponState, build: Build) -> Build:
        resolved_upgrades = []

        for upgrade in build:
            use_defaults = not any(self._key(key) != "rank" for key in upgrade.context)
            context = self._resolve_context(upgrade, weapon, build)
            resolved: dict[str, Value] = {}
            rank = context.get("rank", 0)
            if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0:
                raise ValueError
            if upgrade.max_rank is not None:
                rank = min(rank, upgrade.max_rank)
                context["rank"] = rank
            multiplier = 1.0 if upgrade.max_rank in {None, 0} else (rank + 1) / (upgrade.max_rank + 1)
            for stat, value in upgrade.stats.items():
                self._merge(resolved, stat, self._scale(value, multiplier))
            for stat, (value, required_rank) in upgrade.rank_locked_stats.items():
                if rank >= required_rank:
                    self._merge(resolved, stat, value)

            for stat, (value, condition) in upgrade.conditional_stats.items():
                if self._condition_active(condition, context, use_defaults):
                    self._merge(resolved, stat, self._scale(value, multiplier))

            for stat, (value, condition) in upgrade.stacking_stats.items():
                stack_count = context.get(self._key(condition), (upgrade.max_stacks or 0) if use_defaults else 0)
                if isinstance(stack_count, bool) or not isinstance(stack_count, int) or stack_count < 0:
                    raise ValueError
                if upgrade.max_stacks is not None:
                    stack_count = min(stack_count, upgrade.max_stacks)
                if stack_count:
                    self._merge(resolved, stat, self._scale(value, multiplier) * stack_count)

            resolved_upgrades.append(replace(upgrade, context=context, stats=resolved, rank_locked_stats={}, conditional_stats={}, stacking_stats={}))

        return Build(*resolved_upgrades)
