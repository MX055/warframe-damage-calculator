from __future__ import annotations

from dataclasses import replace

from ..models import Build, Upgrade
from ..models.dist import dist
from ..states import MeleeState, PrimaryState, SecondaryState, WeaponState
from ..utils import DAMAGE_TYPES, Value


class UpgradeResolver:
    AUTOMATIC_CONDITIONS = {
        "primary",
        "rifle",
        "bow",
        "shotgun",
        "sniper",
        "secondary",
        "pistol",
        "melee",
        "sacrificial set",
    }

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())

    def _automatic_context(self, weapon: WeaponState, build: Build) -> dict[str, object]:
        weapon_type = self._normalize(str(weapon.type or ""))
        weapon_types = {weapon_type} if weapon_type else set()

        if isinstance(weapon, PrimaryState):
            weapon_types.add("primary")
        elif isinstance(weapon, SecondaryState):
            weapon_types.add("secondary")
        elif isinstance(weapon, MeleeState):
            weapon_types.add("melee")

        if weapon_type == "bow":
            weapon_types.add("rifle")

        upgrade_names = {self._normalize(upgrade.name or "") for upgrade in build}
        context: dict[str, object] = {name: True for name in weapon_types}
        context["weapon"] = weapon_type
        context["sacrificial set"] = {"sacrificial pressure", "sacrificial steel"}.issubset(upgrade_names)
        return context

    def _resolve_context(self, upgrade: Upgrade, automatic_context: dict[str, object]) -> dict[str, object]:
        context = {self._normalize(key): value for key, value in upgrade.context.items()}
        context.update(automatic_context)
        context.setdefault("rank", upgrade.max_rank or 0)
        return context

    def _condition_active(self, condition: str, context: dict[str, object], use_defaults: bool) -> bool:
        condition = self._normalize(condition)
        default = False if condition in self.AUTOMATIC_CONDITIONS else use_defaults
        return bool(context.get(condition, default))

    @staticmethod
    def _scale(value: Value, multiplier: float) -> Value:
        return value if isinstance(value, bool) else value * multiplier

    @staticmethod
    def _merge(target: dict[str, Value], stat: str, value: Value) -> None:
        if stat in DAMAGE_TYPES:
            value = dist(**{stat: value})
            stat = "damage"
        current = target.get(stat)
        if current is None:
            target[stat] = value
        elif isinstance(current, bool) and isinstance(value, bool):
            target[stat] = current or value
        elif isinstance(current, bool) or isinstance(value, bool):
            raise TypeError(f"Cannot merge values for upgrade stat {stat!r}")
        else:
            try:
                target[stat] = current + value
            except TypeError:
                raise TypeError(f"Cannot merge values for upgrade stat {stat!r}") from None

    def resolve(self, weapon: WeaponState, build: Build) -> Build:
        resolved_upgrades = []
        automatic_context = self._automatic_context(weapon, build)

        for upgrade in build:
            upgrade.validate()
            upgrade_name = upgrade.name or "<unnamed>"
            use_defaults = not any(self._normalize(key) != "rank" for key in upgrade.context)
            context = self._resolve_context(upgrade, automatic_context)
            resolved: dict[str, Value] = {}
            rank = context.get("rank", 0)
            if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0:
                raise ValueError(f"Invalid rank {rank!r} for upgrade {upgrade_name!r}; rank must be a non-negative integer")
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
                normalized_condition = self._normalize(condition)
                stack_count = context.get(normalized_condition, (upgrade.max_stacks or 0) if use_defaults else 0)
                if isinstance(stack_count, bool) or not isinstance(stack_count, int) or stack_count < 0:
                    raise ValueError(f"Invalid stack count {stack_count!r} for condition {condition!r} on upgrade {upgrade_name!r}; stack count must be a non-negative integer")
                if upgrade.max_stacks is not None:
                    stack_count = min(stack_count, upgrade.max_stacks)
                if stack_count:
                    self._merge(resolved, stat, self._scale(value, multiplier) * stack_count)

            resolved_upgrades.append(replace(upgrade, context=context, stats=resolved, rank_locked_stats={}, conditional_stats={}, stacking_stats={}))

        return Build(*resolved_upgrades)
