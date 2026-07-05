from ..models import dist
from .weapon_fields import WeaponFields


class RangedFields(WeaponFields):
    """Keyword fields for ranged weapons.

    Adds ranged inputs such as fire rate, reload speed, magazine size,
    multishot, weakpoint damage, beam behavior, battery behavior, and
    explosion damage.

    These are base weapon stats. ``Build`` and ``Upgrade`` values are applied
    later by the calculator.

    ``PrimaryField`` and ``SecondaryField`` both reuse this ranged field set.
    """
    is_beam: bool
    is_battery: bool
    explosion_damage_dist: dist
    explosion_forced_procs: dist
    multishot: float
    fire_rate: float
    burst_count: int
    burst_delay: float
    charge_time: float
    reload_speed: float
    recharge_rate: float
    magazine_capacity: int
    weakpoint_damage: float