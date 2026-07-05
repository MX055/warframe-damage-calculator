from .ranged_fields import RangedFields


class SecondaryFields(RangedFields):
    """Keyword fields for secondary weapons.

    Secondary weapons currently use the same constructor inputs as other
    ranged weapons, so this class does not add fields beyond ``RangedField``.

    It gives ``Secondary`` its own named input type while keeping the shared
    ranged weapon field set.
    """