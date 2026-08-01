class LoadoutCompatibilityWarning(UserWarning):
    pass


class PerkCompatibilityWarning(LoadoutCompatibilityWarning):
    pass


class ProgenitorCompatibilityWarning(LoadoutCompatibilityWarning):
    pass


class UnimplementedUpgradeWarning(UserWarning):
    pass
