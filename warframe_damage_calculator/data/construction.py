from ..models.melee import Melee
from ..models.primary import Primary
from ..models.secondary import Secondary
from ..models.upgrade import Upgrade
from ..models.weapon import Weapon
from .schema import DatabaseEntry


class DatabaseFactory:
    models = {"primary": Primary, "secondary": Secondary, "melee": Melee, "mod": Upgrade, "arcane": Upgrade}

    def create(self, entry: DatabaseEntry) -> Weapon | Upgrade:
        return self.models[entry.category](entry.data)
