from collections.abc import Iterator, Mapping, MutableMapping
from copy import deepcopy
from typing import ClassVar, Self, get_args, get_origin

from ..utils.types import DataValue, JsonValue, Number
from .dist import Dist


class Data(MutableMapping[str, DataValue]):
    _fields: ClassVar[dict[str, object]] = {}
    _defaults: ClassVar[dict[str, DataValue]] = {}

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        cls._fields = dict(getattr(cls.__base__, "_fields", {}))
        cls._defaults = dict(getattr(cls.__base__, "_defaults", {}))

        for name, annotation in cls.__annotations__.items():
            if name.startswith("_") or get_origin(annotation) is ClassVar:
                continue

            cls._fields[name] = annotation

            if name in cls.__dict__:
                cls._defaults[name] = cls.__dict__[name]
                delattr(cls, name)

    def __init__(self, data: Mapping[str, DataValue] | None = None) -> None:
        object.__setattr__(self, "_values", {})
        object.__setattr__(self, "_default_values", {})
        object.__setattr__(self, "_suppressed_defaults", set())
        self.update(data or {})

    def __getitem__(self, key: str) -> DataValue:
        if key in self._values:
            return self._values[key]
        if key in self._suppressed_defaults or key not in self._defaults:
            raise KeyError(key)
        if key not in self._default_values:
            default = deepcopy(self._defaults[key])
            self._default_values[key] = self._convert_field(key, default)
        return self._default_values[key]

    def __setitem__(self, key: str, value: DataValue) -> None:
        self._suppressed_defaults.discard(key)
        self._default_values.pop(key, None)
        self._values[key] = self._convert_field(key, value)

    def __delitem__(self, key: str) -> None:
        if key in self._values:
            del self._values[key]
        elif key not in self._defaults or key in self._suppressed_defaults:
            raise KeyError(key)
        self._default_values.pop(key, None)
        if key in self._defaults:
            self._suppressed_defaults.add(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return repr(self._values)

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        copied = type(self).__new__(type(self))
        object.__setattr__(copied, "_values", {})
        object.__setattr__(copied, "_default_values", {})
        object.__setattr__(copied, "_suppressed_defaults", self._suppressed_defaults.copy())
        memo[id(self)] = copied
        copied.update(deepcopy(self._values, memo))
        object.__setattr__(copied, "_default_values", deepcopy(self._default_values, memo))
        return copied

    @staticmethod
    def _convert(value: DataValue) -> DataValue:
        if isinstance(value, Data): return value
        if isinstance(value, Mapping): return Data(value)
        if isinstance(value, list): return [Data._convert(item) for item in value]
        return value

    @staticmethod
    def _convert_items(values: list[DataValue], item_type: object) -> list[DataValue]:
        if not isinstance(item_type, type) or not issubclass(item_type, Data):
            return [Data._convert(value) for value in values]

        items: list[DataValue] = []
        for value in values:
            if isinstance(value, item_type):
                items.append(value)
            elif isinstance(value, Mapping):
                items.append(item_type(value))
            else:
                items.append(value)
        return items

    @classmethod
    def _convert_field(cls, key: str, value: DataValue) -> DataValue:
        annotation = cls._fields.get(key)
        if annotation is Dist:
            return Dist(value)
        if isinstance(annotation, type) and issubclass(annotation, Data) and isinstance(value, Mapping):
            return value if isinstance(value, annotation) else annotation(value)
        if get_origin(annotation) is list and isinstance(value, list):
            return cls._convert_items(value, get_args(annotation)[0])
        return cls._convert(value)

    def __getattr__(self, key: str) -> DataValue:
        if key.startswith("_"):
            raise AttributeError(key)
        try: return self[key]
        except KeyError: raise AttributeError(key) from None

    def __setattr__(self, key: str, value: DataValue) -> None:
        self[key] = value

    def __delattr__(self, key: str) -> None:
        try: del self[key]
        except KeyError: raise AttributeError(key) from None

    def __contains__(self, key: object) -> bool:
        return key in self._values

    def __or__(self, other: Mapping[str, DataValue]) -> Self:
        return type(self)(dict(self) | dict(other))

    def __ror__(self, other: Mapping[str, DataValue]) -> Self:
        return type(self)(dict(other) | dict(self))

    def update(self, data: Mapping[str, DataValue], /) -> None:
        for key, value in data.items(): self[key] = value

    def copy(self) -> Self:
        return deepcopy(self)

    def with_defaults(self) -> dict[str, DataValue]:
        values = {key: self[key] for key in self._defaults if key not in self._suppressed_defaults}
        values.update(self._values)
        return values

class ModelData(Data):
    stats: Data = {}
    context: Data = {}


class WeaponContext(Data):
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


class WeaponInputStats(Data):
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


class UpgradeContext(Data):
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
    damage: Dist = Dist()
    elements: Data = Data()
    ammo_efficiency: Number = 0.0
    attack_speed: Number = 0.0
    base_damage: Number = 0.0
    crit_chance: Number = 0.0
    crit_damage: Number = 0.0
    enabled: bool = False
    faction_damage: Number = 0.0
    fire_rate: Number = 0.0
    fire_rate_lock: bool = False
    flat_crit_chance: Number = 0.0
    flat_crit_damage: Number = 0.0
    hunter_munitions: Number = 0.0
    internal_bleeding: Number = 0.0
    magazine_capacity: Number = 0.0
    melee_doughty: Number = 0.0
    melee_duplicate: Number = 0.0
    multiplicative_base_damage: Number = 0.0
    multiplicative_crit_chance: Number = 0.0
    multiplicative_fire_rate: Number = 0.0
    multiplicative_weakpoint_crit_chance: Number = 0.0
    multishot: Number = 0.0
    multishot_lock: bool = False
    primed_chamber: Number = 0.0
    reload_speed: Number = 0.0
    secondary_encumber: Number = 0.0
    secondary_enervate: Number = 0.0
    status_chance: Number = 0.0
    status_damage: Number = 0.0
    vigilante_bonus: Number = 0.0
    weakpoint_crit_chance: Number = 0.0
    weakpoint_damage: Number = 0.0


class BuildData(Data):
    upgrades: list[UpgradeData]
