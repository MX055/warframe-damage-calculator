from .arsenal import Arsenal, arsenal
from .domain.damage import Dist
from .domain.effects import Effect
from .domain.enemies import BodyPart, Enemy, EnemyStats
from .domain.upgrades import Build, Compatibility, Upgrade, UpgradeStats
from .domain.weapons import Attack, AttackStats, BuildCompatibilityWarning, Melee, Primary, Secondary, UnimplementedUpgradeWarning, Weapon, configure_weapon_services
from .engine.weapon_results import WeaponResults
from .formatting import WeaponFormatter

configure_weapon_services(WeaponResults, WeaponFormatter)

__version__ = "0.9.0"

__all__ = ["Arsenal", "Attack", "AttackStats", "BodyPart", "Build", "BuildCompatibilityWarning", "Compatibility", "Dist", "Effect", "Enemy", "EnemyStats", "Melee", "Primary", "Secondary", "UnimplementedUpgradeWarning", "Upgrade", "UpgradeStats", "Weapon", "arsenal"]
