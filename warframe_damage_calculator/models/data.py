from collections.abc import Mapping
from copy import deepcopy
from typing import ClassVar, Self, get_args, get_origin

from ..utils.types import DataValue, JsonValue, Number
from .dist import Dist


class Data(dict[str, DataValue]):
    def __init__(self, data: Mapping[str, DataValue] | None = None) -> None:
        super().__init__()
        self.update(data or {})

    @staticmethod
    def _convert(value: DataValue) -> DataValue:
        if isinstance(value, Data): return value
        if isinstance(value, Mapping): return Data(value)
        if isinstance(value, list): return [Data._convert(item) for item in value]
        return value

    @classmethod
    def _convert_field(cls, key: str, value: DataValue) -> DataValue:
        annotation = next((base.__annotations__[key] for base in cls.__mro__ if key in getattr(base, "__annotations__", {})), None)
        if annotation is Dist:
            return Dist(value)
        if isinstance(annotation, type) and issubclass(annotation, Data) and isinstance(value, Mapping):
            return value if isinstance(value, annotation) else annotation(value)
        if get_origin(annotation) is list and isinstance(value, list):
            item_type = get_args(annotation)[0]
            if isinstance(item_type, type) and issubclass(item_type, Data):
                return [item if isinstance(item, item_type) else item_type(item) if isinstance(item, Mapping) else item for item in value]
        return cls._convert(value)

    def __getattr__(self, key: str) -> DataValue:
        try: return self[key]
        except KeyError: raise AttributeError(key) from None

    def __delattr__(self, key: str) -> None:
        try: del self[key]
        except KeyError: raise AttributeError(key) from None

    def __setattr__(self, key: str, value: DataValue) -> None:
        dict.__setitem__(self, key, self._convert_field(key, value))

    __setitem__ = __setattr__

    def __or__(self, other: Mapping[str, DataValue]) -> Self:
        return type(self)(dict(self) | dict(other))

    def __ror__(self, other: Mapping[str, DataValue]) -> Self:
        return type(self)(dict(other) | dict(self))

    def update(self, data: Mapping[str, DataValue], /) -> None:
        for key, value in data.items(): self[key] = value

    def copy(self) -> Self:
        return deepcopy(self)


class DefaultData(Data):
    _defaults: ClassVar[dict[str, DataValue]] = {}

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        defaults = dict(getattr(cls.__base__, "_defaults", {}))
        for field, annotation in cls.__annotations__.items():
            if field.startswith("_") or get_origin(annotation) is ClassVar or field not in cls.__dict__:
                continue
            defaults[field] = cls.__dict__[field]
            delattr(cls, field)
        cls._defaults = defaults

    def __init__(self, data: Mapping[str, DataValue] | None = None) -> None:
        super().__init__(deepcopy(self._defaults) | dict(data or {}))


class ModelData(Data):
    def __init__(self, data: Mapping[str, DataValue] | None = None) -> None:
        super().__init__({"stats": {}, "context": {}} | dict(data or {}))


class WeaponContext(DefaultData):
    name: str = ""
    category: str = "Weapon"
    type: str = ""


class RangedContext(WeaponContext):
    trigger: str = ""
    is_beam: bool = False
    is_battery: bool = False


class PrimaryContext(RangedContext):
    category: str = "Primary"


class SecondaryContext(RangedContext):
    category: str = "Secondary"


class MeleeContext(WeaponContext):
    category: str = "Melee"


class WeaponInputStats(DefaultData):
    damage: Dist = Dist()
    forced_procs: Dist = Dist()
    crit_chance: Number = 0.0
    crit_damage: Number = 1.0
    status_chance: Number = 0.0


class RangedInputStats(WeaponInputStats):
    explosion_damage: Dist = Dist()
    explosion_forced_procs: Dist = Dist()
    burst_count: int = 1
    burst_delay: Number = 0.0
    charge_time: Number = 0.0
    fire_rate: Number = 0.05
    magazine_capacity: Number = 1
    multishot: Number = 1.0
    recharge_rate: Number = 0.0
    reload_speed: Number = 0.0
    weakpoint_damage: Number = 3.0


class MeleeInputStats(WeaponInputStats):
    attack_speed: Number = 1.0


class WeaponData(ModelData):
    stats: WeaponInputStats
    context: WeaponContext


class RangedData(WeaponData):
    stats: RangedInputStats
    context: RangedContext


class MeleeData(WeaponData):
    stats: MeleeInputStats
    context: MeleeContext


class PrimaryData(RangedData):
    stats: RangedInputStats
    context: PrimaryContext


class SecondaryData(RangedData):
    stats: RangedInputStats
    context: SecondaryContext


class WeaponCalculatedStats(Data):
    damage: Dist
    forced_procs: Dist
    explosion_damage: Dist
    explosion_forced_procs: Dist
    multiplicative_base_damage: Number
    base_damage: Number
    faction_damage: Number
    flat_crit_chance: Number
    multiplicative_crit_chance: Number
    crit_chance: Number
    flat_crit_damage: Number
    crit_damage: Number
    status_chance: Number
    status_damage: Number
    attack_speed: Number
    melee_duplicate: Number
    melee_doughty: Number
    multishot: Number
    fire_rate: Number
    multiplicative_fire_rate: Number
    burst_count: int
    burst_delay: Number
    charge_time: Number
    reload_speed: Number
    recharge_rate: Number
    ammo_efficiency: Number
    magazine_capacity: Number
    weakpoint_damage: Number
    multiplicative_weakpoint_crit_chance: Number
    weakpoint_crit_chance: Number
    internal_bleeding: Number
    hunter_munitions: Number
    primed_chamber: Number
    vigilante_bonus: Number
    secondary_enervate: Number
    secondary_encumber: Number


class WeaponAverageStats(Data):
    crit_chance: Number
    crit_multiplier: Number
    weakpoint_crit_chance: Number
    weakpoint_crit_multiplier: Number
    fire_rate: Number
    procs_per_shot: Number
    beam_dot_multiplier: Number
    flat_dph: Number
    flat_weakpoint_dph: Number
    flat_dps: Number
    flat_weakpoint_dps: Number
    flat_dotph: Number
    flat_weakpoint_dotph: Number
    flat_dotps: Number
    flat_weakpoint_dotps: Number
    total_dph: Number
    total_weakpoint_dph: Number
    total_dps: Number
    total_weakpoint_dps: Number
    melee_doughty_bonus: Number
    melee_duplicate_multiplier: Number
    primed_chamber_multiplier: Number
    secondary_enervate_bonus: Number
    weakpoint_secondary_enervate_bonus: Number


class UpgradeContext(DefaultData):
    name: str = ""
    category: str = "Upgrade"
    type: str = ""
    compatibility: list[str] = []
    incompatibility: list[str] = []
    requirements: Mapping[str, JsonValue] = {}
    max_rank: int | None = None
    max_stacks: int | None = None
    rank: int
    stacks: int
    is_exilus: bool = False
    weapon: str
    primary: bool
    rifle: bool
    bow: bool
    shotgun: bool
    sniper: bool
    secondary: bool
    pistol: bool
    melee: bool


class UpgradeStatValues(Data):
    ammo_efficiency: JsonValue
    attack_speed: JsonValue
    base_damage: JsonValue
    cold: JsonValue
    corrosive: JsonValue
    crit_chance: JsonValue
    crit_damage: JsonValue
    damage: JsonValue
    electricity: JsonValue
    elements: JsonValue
    enabled: JsonValue
    faction_damage: JsonValue
    fire_rate: JsonValue
    fire_rate_lock: JsonValue
    flat_crit_chance: JsonValue
    flat_crit_damage: JsonValue
    gas: JsonValue
    heat: JsonValue
    hunter_munitions: JsonValue
    impact: JsonValue
    internal_bleeding: JsonValue
    magazine_capacity: JsonValue
    magnetic: JsonValue
    melee_doughty: JsonValue
    melee_duplicate: JsonValue
    multiplicative_base_damage: JsonValue
    multiplicative_crit_chance: JsonValue
    multiplicative_fire_rate: JsonValue
    multiplicative_weakpoint_crit_chance: JsonValue
    multishot: JsonValue
    multishot_lock: JsonValue
    primed_chamber: JsonValue
    puncture: JsonValue
    radiation: JsonValue
    reload_speed: JsonValue
    secondary_encumber: JsonValue
    secondary_enervate: JsonValue
    slash: JsonValue
    status_chance: JsonValue
    status_damage: JsonValue
    toxin: JsonValue
    vigilante_bonus: JsonValue
    viral: JsonValue
    weakpoint_crit_chance: JsonValue
    weakpoint_damage: JsonValue


class UpgradeData(ModelData):
    stats: UpgradeStatValues
    context: UpgradeContext


class ResolvedStatValues(Data):
    damage: Dist
    elements: Data
    ammo_efficiency: Number
    attack_speed: Number
    base_damage: Number
    crit_chance: Number
    crit_damage: Number
    enabled: bool
    faction_damage: Number
    fire_rate: Number
    fire_rate_lock: bool
    flat_crit_chance: Number
    flat_crit_damage: Number
    hunter_munitions: Number
    internal_bleeding: Number
    magazine_capacity: Number
    melee_doughty: Number
    melee_duplicate: Number
    multiplicative_base_damage: Number
    multiplicative_crit_chance: Number
    multiplicative_fire_rate: Number
    multiplicative_weakpoint_crit_chance: Number
    multishot: Number
    multishot_lock: bool
    primed_chamber: Number
    reload_speed: Number
    secondary_encumber: Number
    secondary_enervate: Number
    status_chance: Number
    status_damage: Number
    vigilante_bonus: Number
    weakpoint_crit_chance: Number
    weakpoint_damage: Number

    def __init__(self, data: Mapping[str, DataValue] | None = None, *, defaults: bool = True) -> None:
        if not defaults:
            super().__init__(data)
            return
        defaults = {field: Dist() if kind is Dist else Data() if kind is Data else False if kind is bool else 0.0 for field, kind in type(self).__annotations__.items()}
        super().__init__(defaults | dict(data or {}))


class BuildData(Data):
    upgrades: list[UpgradeData]
