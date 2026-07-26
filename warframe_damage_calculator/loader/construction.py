from collections.abc import Mapping
from numbers import Number
from typing import Any

from ..models.upgrade import Upgrade
from ..models.weapon import Weapon
from ..models.melee import Melee
from ..models.primary import Primary
from ..models.secondary import Secondary
from .schema import DatabaseEntry


class DatabaseFactory:
    models = {"primary": Primary, "secondary": Secondary, "melee": Melee, "mod": Upgrade, "arcane": Upgrade}

    @staticmethod
    def _apply_effect_defaults(runtime: dict[str, Any], stats: Mapping[str, Any]) -> None:
        for raw in stats.values():
            for effect in raw if isinstance(raw, list) else (raw,):
                if not isinstance(effect, Mapping): continue
                condition = effect.get("when")
                if condition is not None: runtime[str(condition)] = True
                stacks = effect.get("stacks")
                if isinstance(stacks, Mapping):
                    key = str(stacks.get("when", "stacks"))
                    maximum = stacks.get("max", 0)
                    if isinstance(maximum, Number): runtime[key] = max(runtime.get(key, 0), maximum)

    @classmethod
    def _default_weapon_runtime(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        runtime: dict[str, Any] = {"attack": next(iter(data["attacks"])), "evolutions": {}, "combo": 1, "stance_combo": "neutral", "ability_strength": 1.0}
        for tier in data.get("evolutions", {}).values():
            for perk in tier.values():
                cls._apply_effect_defaults(runtime, perk.get("stats", {}))
        return runtime

    @classmethod
    def _default_upgrade_runtime(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        runtime: dict[str, Any] = {"rank": data.get("max_rank", 0)}
        cls._apply_effect_defaults(runtime, data.get("stats", {}))
        return runtime

    def create(self, entry: DatabaseEntry, context: dict | None = None) -> Weapon | Upgrade:
        runtime = self._default_weapon_runtime(entry.data) if entry.is_weapon else self._default_upgrade_runtime(entry.data)
        runtime.update(entry.data.get("runtime", {}))
        if context: runtime.update(context)
        return self.models[entry.category]({**entry.data, "runtime": runtime})
