from ..models.upgrade import Upgrade
from ..models.weapon import Weapon
from ..models.melee import Melee
from ..models.primary import Primary
from ..models.secondary import Secondary
from .schema import DatabaseEntry


class DatabaseFactory:
    models = {"primary": Primary, "secondary": Secondary, "melee": Melee, "mod": Upgrade, "arcane": Upgrade}

    def create(self, entry: DatabaseEntry, context: dict | None = None) -> Weapon | Upgrade:
        model = self.models[entry.category](entry.data)
        if context:
            if isinstance(model, Upgrade):
                model.data.runtime.update(context)
                model.results.resolve()
            else:
                model.data.update(context)
                model.results.recompute()
        return model
