from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .damage import Dist
from .effects import Automatic
from .scaled_values import is_scaled_value_record

PARENT_SELECTOR_FIELDS = frozenset({"names", "triggers", "deliveries", "forms", "categories", "aoe"})
RELATED_ATTACK_FIELDS = PARENT_SELECTOR_FIELDS
ATTACK_RECORD_FIELDS = frozenset({"name", "trigger", "delivery", "form", "category", "aoe", "hits_source", "children", "stats"})
INHERITANCE_TOP_LEVEL = frozenset({"trigger", "delivery", "form", "category", "aoe", "hits_source", "stats"})
FALLOFF_FIELDS = frozenset({"start_range", "end_range", "final_multiplier"})


def _contains_attack_expressions(value: object) -> bool:
    if isinstance(value, Mapping):
        if "source" in value or is_scaled_value_record(value): return True
        return any(_contains_attack_expressions(item) for item in value.values())
    if isinstance(value, list): return any(_contains_attack_expressions(item) for item in value)
    return False


def _stats_from_record(record: Mapping[str, Any] | None) -> AttackStats | dict[str, Any]:
    raw = dict(record or {})
    if _contains_attack_expressions(raw): return raw
    return AttackStats.from_record(raw)


def _parse_children(value: object) -> list[str]:
    if value is None: return []
    if not isinstance(value, list): raise TypeError("attack children must be a list of names")
    if any(not isinstance(item, str) or not item for item in value): raise ValueError("attack children must be a list of nonempty strings")
    return [str(item) for item in value]


@dataclass(slots=True)
class Falloff:
    start_range: float = 0
    end_range: float | None = None
    final_multiplier: float = 1

    def __post_init__(self) -> None:
        self.start_range = float(self.start_range)
        self.end_range = None if self.end_range is None else float(self.end_range)
        self.final_multiplier = float(self.final_multiplier)
        if self.start_range < 0: raise ValueError("falloff start_range must be nonnegative")
        if self.end_range is not None and self.end_range < 0: raise ValueError("falloff end_range must be nonnegative")
        if not 0 <= self.final_multiplier <= 1: raise ValueError("falloff final_multiplier must be between 0 and 1")
        if self.end_range is not None and self.start_range > self.end_range: raise ValueError("falloff ranges must satisfy start_range <= end_range")

    def __bool__(self) -> bool:
        return self.end_range is not None

    @classmethod
    def from_record(cls, record: Mapping[str, Any] | None) -> Falloff | None:
        if record is None: return None
        if not isinstance(record, Mapping): raise TypeError("falloff must be an object")
        if not record: return None
        if set(record) - FALLOFF_FIELDS: raise ValueError(f"unknown falloff fields: {sorted(set(record) - FALLOFF_FIELDS)}")
        end_range = record.get("end_range")
        final_multiplier = record.get("final_multiplier")
        return cls(
            start_range=float(record.get("start_range") or 0),
            end_range=None if end_range is None else float(end_range),
            final_multiplier=1.0 if final_multiplier is None else float(final_multiplier),
        )

    def to_record(self) -> dict[str, float]:
        if self.end_range is None: return {}
        return {"start_range": self.start_range, "end_range": self.end_range, "final_multiplier": self.final_multiplier}


@dataclass(slots=True)
class AttackStats:
    ammo_cost: float = 1
    damage: Dist = field(default_factory=Dist)
    forced_procs: Dist = field(default_factory=Dist)
    punch_through: float | str = 0
    crit_chance: float = 0
    crit_damage: float = 1
    status_chance: float = 0
    status_duration: float = 6
    multishot: float = 1
    fire_rate: float = 0.05
    attack_speed: float | None = None
    burst_count: int = 1
    burst_delay: float = 0
    charge_time: float = 0
    co_factor: float = 1
    co_effect: str = "adds"
    range: float = 0
    max_range: float | None = None
    damage_bonus: float = 0
    initial_combo: float = 0
    heavy_attack_efficiency: float = 0
    zoom: float = 0
    accuracy: float = 0
    recoil: float = 0
    noise_level: str = "alarming"
    falloff: Falloff | None = None

    def __post_init__(self) -> None:
        self.punch_through = float(self.punch_through)
        if isinstance(self.falloff, Mapping): self.falloff = Falloff.from_record(self.falloff)
        if self.punch_through < 0: raise ValueError("punch_through must be nonnegative")
        if self.range < 0: raise ValueError("range must be nonnegative")
        if self.max_range is not None and self.max_range < 0: raise ValueError("max_range must be nonnegative")
        if self.falloff is None or self.falloff.end_range is None: return
        maximum = self.falloff.end_range if self.max_range is None else self.max_range
        if not 0 <= self.falloff.start_range <= self.falloff.end_range <= maximum: raise ValueError("falloff ranges must satisfy 0 <= start_range <= end_range <= max_range")

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> AttackStats:
        values = dict(record)
        values["damage"] = Dist(values.get("damage", {}))
        values["forced_procs"] = Dist(values.get("forced_procs", {}))
        values["falloff"] = Falloff.from_record(values.get("falloff"))
        return cls(**values)

    def to_record(self) -> dict[str, Any]:
        blank = AttackStats()
        record: dict[str, Any] = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            default = getattr(blank, field_name)
            if isinstance(value, Dist):
                if value: record[field_name] = dict(value)
            elif isinstance(value, Falloff):
                if value: record[field_name] = value.to_record()
            elif isinstance(value, Mapping):
                if value: record[field_name] = dict(value)
            elif value != default:
                record[field_name] = value
        return record


def _validate_inheritance_path(path: str, *, label: str) -> None:
    if not isinstance(path, str) or not path: raise ValueError(f"attack inheritance {label} must be nonempty paths")
    if path == "*": raise ValueError("attack inheritance wildcard is not supported")
    parts = path.split(".")
    nested_mappings = {"damage", "forced_procs", "falloff"}
    stat_fields = set(AttackStats.__dataclass_fields__)
    if any(not part for part in parts) or parts[0] not in INHERITANCE_TOP_LEVEL: raise ValueError(f"invalid attack inheritance field {path!r}")
    if len(parts) == 1: return
    if parts[0] != "stats" or parts[1] not in stat_fields or len(parts) > 3 or len(parts) == 3 and parts[1] not in nested_mappings: raise ValueError(f"invalid attack inheritance field {path!r}")
    if len(parts) == 3 and parts[1] == "falloff" and parts[2] not in FALLOFF_FIELDS: raise ValueError(f"invalid attack inheritance field {path!r}")


def _validate_override_paths(override: Mapping[str, Any]) -> None:
    paths = [str(path) for path in override]
    for path in paths: _validate_inheritance_path(path, label="override")
    for index, path in enumerate(paths):
        prefix = path + "."
        for other in paths[index + 1:]:
            if other.startswith(prefix) or path.startswith(other + "."):
                raise ValueError(f"attack inheritance override paths conflict: {path!r} and {other!r}")


@dataclass(slots=True)
class Inheritance:
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    override: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.include = [str(path) for path in self.include]
        self.exclude = [str(path) for path in self.exclude]
        if isinstance(self.override, Mapping): self.override = {str(path): deepcopy(value) for path, value in self.override.items()}
        else: raise TypeError("attack inheritance override must be an object")
        if not self.include and self.exclude: raise ValueError("attack inheritance exclude requires include")
        for path in self.include: _validate_inheritance_path(path, label="include")
        for path in self.exclude: _validate_inheritance_path(path, label="exclude")
        _validate_override_paths(self.override)

    def __bool__(self) -> bool:
        return bool(self.include or self.exclude or self.override)

    @classmethod
    def from_record(cls, record: Mapping[str, object] | None) -> Inheritance | None:
        if record is None: return None
        if set(record) - {"include", "exclude", "override"}: raise ValueError("attack inheritance only supports include, exclude, and override")
        include = record.get("include", [])
        exclude = record.get("exclude", [])
        override = record.get("override", {})
        if not isinstance(include, list) or not isinstance(exclude, list): raise TypeError("attack inheritance include/exclude must be lists")
        if any(not isinstance(path, str) for path in (*include, *exclude)): raise TypeError("attack inheritance paths must be strings")
        if override is None: override = {}
        if not isinstance(override, Mapping): raise TypeError("attack inheritance override must be an object")
        if any(not isinstance(path, str) or not path for path in override): raise TypeError("attack inheritance override keys must be nonempty strings")
        if not include and not exclude and not override: return None
        return cls(list(include), list(exclude), dict(override))

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {}
        if self.include: record["include"] = list(self.include)
        if self.exclude: record["exclude"] = list(self.exclude)
        if self.override: record["override"] = deepcopy(self.override)
        return record

    def copy(self) -> Inheritance:
        return Inheritance(list(self.include), list(self.exclude), deepcopy(self.override))


@dataclass(slots=True)
class RelatedAttacks:
    names: list[str] | None = None
    triggers: list[str] | None = None
    deliveries: list[str] | None = None
    forms: list[str] | None = None
    categories: list[str] | None = None
    aoe: bool | None = None

    def __post_init__(self) -> None:
        present = {key: value for key, value in (("names", self.names), ("triggers", self.triggers), ("deliveries", self.deliveries), ("forms", self.forms), ("categories", self.categories), ("aoe", self.aoe)) if value is not None}
        if not present: raise ValueError("related attacks selector requires at least one field")
        for key in ("names", "triggers", "deliveries", "forms", "categories"):
            values = getattr(self, key)
            if values is None: continue
            if not isinstance(values, list) or not values or any(not isinstance(item, str) or not item for item in values): raise ValueError(f"related attacks.{key} must be a nonempty list of strings")
            setattr(self, key, list(values))
        if self.aoe is not None and not isinstance(self.aoe, bool): raise TypeError("related attacks.aoe must be a bool")

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> RelatedAttacks:
        if not isinstance(record, Mapping) or set(record) - RELATED_ATTACK_FIELDS or not record: raise ValueError("related attacks requires a nonempty attack selector")
        return cls(
            names=None if "names" not in record else list(record["names"]),  # type: ignore[arg-type]
            triggers=None if "triggers" not in record else list(record["triggers"]),  # type: ignore[arg-type]
            deliveries=None if "deliveries" not in record else list(record["deliveries"]),  # type: ignore[arg-type]
            forms=None if "forms" not in record else list(record["forms"]),  # type: ignore[arg-type]
            categories=None if "categories" not in record else list(record["categories"]),  # type: ignore[arg-type]
            aoe=None if "aoe" not in record else bool(record["aoe"]),
        )

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {}
        if self.names is not None: record["names"] = list(self.names)
        if self.triggers is not None: record["triggers"] = list(self.triggers)
        if self.deliveries is not None: record["deliveries"] = list(self.deliveries)
        if self.forms is not None: record["forms"] = list(self.forms)
        if self.categories is not None: record["categories"] = list(self.categories)
        if self.aoe is not None: record["aoe"] = self.aoe
        return record

    def copy(self) -> RelatedAttacks:
        return RelatedAttacks(names=None if self.names is None else list(self.names), triggers=None if self.triggers is None else list(self.triggers), deliveries=None if self.deliveries is None else list(self.deliveries), forms=None if self.forms is None else list(self.forms), categories=None if self.categories is None else list(self.categories), aoe=self.aoe)

    def matches(self, key: str, attack: Attack) -> bool:
        if self.names is not None:
            expected = {item.casefold() for item in self.names}
            if key.casefold() not in expected and attack.name.casefold() not in expected: return False
        fields = {"triggers": attack.trigger, "deliveries": attack.delivery, "forms": attack.form, "categories": attack.category}
        for field_name, actual in fields.items():
            expected_values = getattr(self, field_name)
            if expected_values is not None and actual not in expected_values: return False
        return self.aoe in (None, attack.aoe)


@dataclass(slots=True)
class Attack:
    name: str
    trigger: str | None = None
    delivery: str | None = None
    form: str = "normal"
    category: str = "normal"
    aoe: bool = False
    hits_source: bool = True
    children: list[str] = field(default_factory=list)
    stats: AttackStats | dict[str, Any] = field(default_factory=AttackStats)

    def __post_init__(self) -> None:
        self.name = str(self.name)
        if not self.name: raise ValueError("attack name is required")
        self.children = _parse_children(self.children)
        if isinstance(self.stats, Mapping) and not isinstance(self.stats, AttackStats):
            self.stats = _stats_from_record(self.stats)

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Attack:
        if "links" in record: raise ValueError("attack field 'links' was removed; use children")
        if "parent" in record: raise ValueError("attack field 'parent' is only valid on generated attacks")
        if "inheritance" in record: raise ValueError("attack field 'inheritance' is only valid on generated attacks")
        if "automatic" in record: raise ValueError("attack field 'automatic' is only valid on generated attacks")
        if set(record) - ATTACK_RECORD_FIELDS: raise ValueError(f"unknown attack fields: {sorted(set(record) - ATTACK_RECORD_FIELDS)}")
        values = dict(record)
        values["name"] = str(values["name"])
        values["children"] = _parse_children(values.get("children"))
        values["stats"] = _stats_from_record(values.get("stats", {}))
        return cls(**values)

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {"name": self.name}
        if self.trigger is not None: record["trigger"] = self.trigger
        if self.delivery is not None: record["delivery"] = self.delivery
        if self.form != "normal": record["form"] = self.form
        if self.category != "normal": record["category"] = self.category
        if self.aoe: record["aoe"] = True
        if not self.hits_source: record["hits_source"] = False
        if self.children: record["children"] = list(self.children)
        if isinstance(self.stats, AttackStats):
            stats = self.stats.to_record()
        else:
            stats = deepcopy(dict(self.stats))
        if stats: record["stats"] = stats
        return record

    def copy(self) -> Attack:
        return Attack(name=self.name, trigger=self.trigger, delivery=self.delivery, form=self.form, category=self.category, aoe=self.aoe, hits_source=self.hits_source, children=list(self.children), stats=self.stats if isinstance(self.stats, AttackStats) else deepcopy(dict(self.stats)))

    def add_child_key(self, key: str) -> None:
        expected = key.casefold()
        if any(child.casefold() == expected for child in self.children): return
        self.children = [*self.children, key]


def match_related_keys(selector: RelatedAttacks, attacks: Mapping[str, Attack]) -> list[str]:
    return [key for key, attack in attacks.items() if selector.matches(key, attack)]


def resolve_child_keys(children: list[str], attacks: Mapping[str, Attack]) -> list[str]:
    if not children: return []
    resolved: list[str] = []
    for name in children:
        matches = match_related_keys(RelatedAttacks(names=[name]), attacks)
        if not matches: raise ValueError(f"unknown child attack {name!r}")
        if len(matches) > 1: raise ValueError(f"child attack {name!r} matches multiple attacks: {', '.join(matches)}")
        if matches[0] not in resolved: resolved.append(matches[0])
    return resolved
