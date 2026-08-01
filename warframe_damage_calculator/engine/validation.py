import warnings

from ..database.compatibility import is_upgrade_compatible
from ..domain.implementation import ImplementationStatus, ImplementationWarning
from ..domain.loadouts import Loadout
from ..domain.warnings import LoadoutCompatibilityWarning, ProgenitorCompatibilityWarning, UnimplementedUpgradeWarning
from ..domain.weapons import Weapon


def warn_implementation(name: str, status: ImplementationStatus, *, stacklevel: int = 3) -> None:
    if status.state == "implemented": return
    details = ", ".join(status.missing_features)
    warnings.warn(f"{name} implementation is {status.state}; missing features: {details}.", ImplementationWarning, stacklevel=stacklevel)


def warn_loadout(weapon: Weapon, loadout: Loadout) -> None:
    warn_implementation(weapon.name, weapon.implementation_status, stacklevel=4)
    previous = []
    for upgrade in loadout.ranked_upgrades:
        if not upgrade.implemented:
            warn_implementation(upgrade.name, upgrade.implementation_status, stacklevel=4)
            if upgrade.implementation_status.state == "not_implemented": warnings.warn(f"{upgrade.name} is not implemented and may not affect calculated results.", UnimplementedUpgradeWarning, stacklevel=3)
        if not is_upgrade_compatible(upgrade, weapon): warnings.warn(f"{upgrade.name} is not compatible with {weapon.name}", LoadoutCompatibilityWarning, stacklevel=3)
        conflicts = {other.name for other in previous if other.name in upgrade.conflicts or upgrade.name in other.conflicts}
        if conflicts: warnings.warn(f"{upgrade.name} conflicts with {', '.join(sorted(conflicts))}", LoadoutCompatibilityWarning, stacklevel=3)
        previous.append(upgrade)
    supports_progenitor = "progenitor" in weapon.traits
    if loadout.progenitor is not None and not supports_progenitor: warnings.warn(f"{weapon.name} does not support progenitor bonuses; the selected progenitor will be ignored.", ProgenitorCompatibilityWarning, stacklevel=3)
