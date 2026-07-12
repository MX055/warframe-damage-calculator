from __future__ import annotations

from ..models import dist, Build, StatValue
from ..states import WeaponState
from ..utils import DAMAGE_TYPES


class UpgradeResolver:
    """Resolve upgrade buckets into the flat stat dictionary calculators consume."""

    WEAPON_CONDITIONS = {"primary", "rifle", "bow", "shotgun", "sniper", "secondary", "pistol", "melee"}

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

    def _condition_active(self, condition: str, weapon: WeaponState, build: Build, context: dict[str, bool | int], default: bool) -> bool:
        condition = self._key(condition)
        if condition in self.WEAPON_CONDITIONS:
            return condition in self._weapon_context(weapon)
        if condition == "sacrificial set":
            names = {self._key(upgrade.name or "") for upgrade in build}
            return {"sacrificial pressure", "sacrificial steel"}.issubset(names)
        manual = {self._key(key): value for key, value in context.items()}
        return bool(manual.get(condition, default))

    @staticmethod
    def _merge(target: dict[str, StatValue], stat: str, value: StatValue) -> None:
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
            raise TypeError(f"Cannot merge values for upgrade stat {stat!r}")

    def resolve(self, weapon: WeaponState, build: Build, context: dict[str, bool | int] | None = None) -> dict[str, StatValue]:
        use_defaults = context is None
        context = dict(context or {})
        manual = {self._key(key): value for key, value in context.items()}
        resolved: dict[str, StatValue] = {}

        for upgrade in build:
            for stat, value in upgrade.stats.items():
                self._merge(resolved, stat, value)

            for stat, (value, condition) in upgrade.conditional_stats.items():
                if self._condition_active(condition, weapon, build, context, use_defaults):
                    self._merge(resolved, stat, value)

            for stat, (value, condition) in upgrade.stacking_stats.items():
                default_stacks = upgrade.max_stacks or 0 if use_defaults else 0
                stack_count = manual.get(self._key(condition), default_stacks)
                if isinstance(stack_count, bool) or not isinstance(stack_count, int) or stack_count < 0:
                    raise ValueError(f"Invalid stack count for condition {condition!r}: {stack_count!r}")
                if upgrade.max_stacks is not None:
                    stack_count = min(stack_count, upgrade.max_stacks)
                if stack_count:
                    self._merge(resolved, stat, value * stack_count)

        return resolved
