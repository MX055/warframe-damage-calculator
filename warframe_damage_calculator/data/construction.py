from ..models import Melee, Primary, Secondary, Upgrade, Weapon
from .schema import DatabaseEntry


class DatabaseFactory:
    models = {"primary": Primary, "secondary": Secondary, "melee": Melee, "mod": Upgrade, "arcane": Upgrade}

    def create(self, entry: DatabaseEntry) -> Weapon | Upgrade:
        return self.models[entry.category](entry.data)
