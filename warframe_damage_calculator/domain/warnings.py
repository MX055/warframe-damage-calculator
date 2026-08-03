class BuildCompatibilityWarning(UserWarning):
    pass


class PerkCompatibilityWarning(BuildCompatibilityWarning):
    pass


class ProgenitorCompatibilityWarning(BuildCompatibilityWarning):
    pass


class UnimplementedUpgradeWarning(UserWarning):
    pass
