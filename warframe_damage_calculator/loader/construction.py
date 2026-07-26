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
    def _default_upgrade_runtime(data: Mapping[str, Any]) -> dict[str, Any]:
        runtime: dict[str, Any] = {"rank": data.get("max_rank", 0)}
        max_stacks: Number = 0
        for raw in data.get("stats", {}).values():
            for effect in raw if isinstance(raw, list) else (raw,):
                if not isinstance(effect, Mapping): continue
                condition = effect.get("when")
                if condition is not None: runtime[str(condition)] = True
                stacks = effect.get("stacks")
                if isinstance(stacks, Mapping) and isinstance(stacks.get("max"), Number): max_stacks = max(max_stacks, stacks["max"])
        if max_stacks: runtime["stacks"] = max_stacks
        return runtime

    def create(self, entry: DatabaseEntry, context: dict | None = None) -> Weapon | Upgrade:
        runtime = {} if entry.is_weapon else self._default_upgrade_runtime(entry.data)
        runtime.update(entry.data.get("runtime", {}))
        if context: runtime.update(context)
        return self.models[entry.category]({**entry.data, "runtime": runtime})
