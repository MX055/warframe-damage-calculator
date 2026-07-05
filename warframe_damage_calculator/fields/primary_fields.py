from .ranged_fields import RangedFields


class PrimaryFields(RangedFields):
    """Keyword fields for primary weapons.

    Primary weapons currently use the same constructor inputs as other ranged
    weapons, so this class does not add fields beyond ``RangedField``.

    It gives ``Primary`` its own named input type while keeping the shared
    ranged weapon field set.
    """