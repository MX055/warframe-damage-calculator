from .weapon_fields import WeaponFields


class MeleeFields(WeaponFields):
    """Keyword fields for melee weapons.

    Adds the melee-only ``attack_speed`` value to the fields shared by all
    weapons.

    These are base weapon stats. ``Build`` and ``Upgrade`` values are applied
    later by the calculator.
    """
    attack_speed: float