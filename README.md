# Warframe Damage Calculator

> Deterministic expected-value damage calculations for Warframe weapons.

**Warframe Damage Calculator** is a Python library for constructing Warframe
weapons and upgrades, combining them into builds, and calculating average damage
per hit and DPS without Monte Carlo simulation.

Version **0.8.0** introduces a new canonical model layout built around the
single-file database schema. Weapons now contain named attack modes, global ammo
data, related child attacks, and optional Incarnon evolutions. Upgrades use the
same named-entry construction style and keep runtime rank, condition, and stack
values separate from their permanent database data.

The project is currently **alpha software**. It is useful for theorycrafting,
build comparison, custom mechanics, database tooling, and external calculator
front ends, but it is not a complete simulation of Warframe combat.

---

## v0.8.0 Highlights

- One canonical database file: `database/database.json`
- New database-shaped constructors for weapons and upgrades
- Multiple named attack modes per weapon
- Runtime attack switching with `weapon.set_mode()`
- Automatic calculation of related child attacks, such as projectiles and their explosions
- Global weapon data separated from attack-specific stats
- Incarnon evolution selection with `weapon.set_evolutions()`
- Attack-specific Condition Overload factors and additive or multiplicative behavior
- Separate faction-damage stats for Corpus, Grineer, Infested, Murmur, Orokin, and Sentient
- `Weapon` added to the package-root public API
- Literal-typed bundled names for better editor inference from `arsenal.get()`
- A single canonical `Build.upgrades` collection
- Detached build and upgrade copies through `Upgrade.copy()` and `Build.copy()`
- Updated ranged summaries that include related attack damage
- A current database containing 656 weapons, 2,234 attack definitions, 763 upgrades, and 92 weapons with evolution data

---

## Features

### Weapon modeling

- `Primary`, `Secondary`, and `Melee` weapon models
- Multiple attacks per weapon, including normal fire, alternate fire, charged attacks, Incarnon forms, slam attacks, and other database-defined modes
- Direct attacks and linked child attacks such as radial explosions
- Hitscan, projectile, beam, melee, and area-of-effect metadata
- Physical, elemental, combined elemental, Void, and Tau damage
- Ordered elemental combination
- Critical chance, critical damage, status chance, and forced procs
- Native and modded multishot
- Weakpoint damage and weakpoint critical chance
- Burst, charge, magazine, reload, battery, ammo-efficiency, and fire-rate calculations
- Beam-specific multishot and ammo behavior
- Fire-rate and multishot locks
- Incarnon evolution selection
- Attack-specific Condition Overload scaling

### Upgrade resolution

- Static effects
- Conditional effects
- Stacking effects with named stack conditions
- Proportional rank scaling
- Rank-locked effects
- Effects that require other equipped upgrades
- Scalar, record, and mixed-list stat syntax
- Automatic weapon-category conditions during build resolution
- Separate `static`, `conditional`, `modular`, `stacking`, `rank_locked`, and `total` result buckets
- Runtime rank, condition, and stack values that do not modify the canonical upgrade entry

### Special mechanics

- Condition Overload and Galvanized status-type damage
- Hunter Munitions
- Internal Bleeding and Hemorrhage
- Primed Chamber and Charged Chamber
- Vigilante set bonus
- Secondary Enervate
- Secondary Encumber
- Melee Duplicate
- Melee Doughty bonus calculation
- Sacrificial equipped-set bonuses
- Faction damage with the largest applicable faction bonus used by the calculator

### Data and API

- Single-file weapon, upgrade, and Riven-stat database
- Normalized name lookup
- Weapon, upgrade, category, subtype, and compatibility filters
- Attribute-only database queries
- Custom single-file databases
- Fresh model construction on every database lookup
- Build composition with `+` and `-`
- Upgrade contribution estimates
- Human-readable ranged and melee summaries
- Typed, sparse, mutable nested data with attribute access
- Detached deep copies of model data
- Damage-distribution helpers for totals, weights, filtering, arithmetic, and elemental combination

---

## Requirements

- Python **3.14+**

---

## Public API

The package root exports the primary model and loader objects:

```python
from warframe_damage_calculator import (
    Build,
    Melee,
    Primary,
    Secondary,
    Upgrade,
    Weapon,
    arsenal,
)
```

`Primary`, `Secondary`, and `Melee` inherit from `Weapon`. `Data`, `Dist`, the
calculator classes, and `WarframeDatabase` remain available from their internal
modules for advanced use, but they are not package-root exports.

---

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/MX055/warframe-damage-calculator.git
```

Development install:

```bash
git clone https://github.com/MX055/warframe-damage-calculator.git
cd warframe-damage-calculator
pip install -e .
```

---

## Quick Start

```python
from warframe_damage_calculator import Build, Primary, Upgrade, arsenal

weapon = arsenal.get("Corinth Prime")
assert isinstance(weapon, Primary)

build = Build(
    arsenal.get("Galvanized Hell", context={"stacks": 4}),
    arsenal.get("Primed Chilling Grasp"),
    arsenal.get("Critical Deceleration"),
)

weapon.configure(build)

print(weapon.format.summary())
print(f"Average DPS:   {weapon.stats.average.total_dps:.2f}")
print(f"Weakpoint DPS: {weapon.stats.average.total_weakpoint_dps:.2f}")
```

Database upgrades resolve at maximum rank and, where applicable, maximum stacks
by default. Pass runtime values through `context` to override that behavior.

---

## Core Workflow

### Load a weapon and inspect its attacks

```python
from warframe_damage_calculator import Primary, arsenal

weapon = arsenal.get("Corinth Prime")
assert isinstance(weapon, Primary)

print(weapon.data.name)
print(list(weapon.data.entry.attacks))
print(weapon.mode.stats.damage)
```

The first attack in the weapon entry is selected by default.

### Select another attack mode

```python
weapon.set_mode("Air Burst Projectile")

print(weapon.mode.trigger)
print(weapon.mode.delivery)
print(weapon.mode.children)
```

Mode names are normalized, so spaces, hyphens, case, and underscore-separated
identifiers can refer to the same attack. An unknown mode raises `ValueError`
and lists the available attacks.

### Configure a build

```python
from warframe_damage_calculator import Build, arsenal

build = Build(
    arsenal.get("Galvanized Hell", context={"stacks": 4}),
    arsenal.get("Primary Merciless", context={"stacks": 12}),
    arsenal.get("Hunter Munitions"),
)

weapon.configure(build)
```

`configure()` accepts one `Build`, or no argument to clear the active build:

```python
weapon.configure()
```

It returns the weapon, so calls can be chained:

```python
weapon = (
    arsenal.get("Corinth Prime")
    .set_mode("Air Burst Projectile")
    .configure(build)
)
```

### Select Incarnon evolutions

```python
weapon = arsenal.get("Telos Boltor")
weapon.set_evolutions(evolution_2=1, evolution_3=2)
weapon.set_mode("Incarnon Form")

print(weapon.evolutions)
print(weapon.stats.parent.effective.damage.total_damage())
```

Selections are validated against the weapon's evolution tiers and perks. Each
selected evolution is converted into an internal upgrade and included when the
weapon is recomputed.

### Read results

```python
print(weapon.stats.parent.base)
print(weapon.stats.parent.modded)
print(weapon.stats.parent.effective)
print(weapon.stats.average)

print(weapon.stats.average.total_dph)
print(weapon.stats.average.total_dps)
print(weapon.format.summary())
```

---

## New Model Construction

Version 0.8.0 constructors use the same named-entry shape as the database. A
model receives a mapping whose top-level key is the model name and whose value
is its canonical entry.

### Constructing a ranged weapon

```python
from warframe_damage_calculator import Primary

weapon = Primary(
    {
        "Example Rifle": {
            "type": "primary",
            "subtype": "rifle",
            "disposition": 1.0,
            "ammo": {
                "reload_time": 2.2,
                "magazine_size": 30,
            },
            "attacks": {
                "normal_attack": {
                    "trigger": "auto",
                    "delivery": "hitscan",
                    "stats": {
                        "damage": {
                            "impact": 20,
                            "puncture": 30,
                            "slash": 50,
                        },
                        "forced_procs": {"slash": 1},
                        "crit_chance": 0.30,
                        "crit_damage": 2.2,
                        "status_chance": 0.25,
                        "multishot": 1,
                        "fire_rate": 6.0,
                    },
                }
            },
        }
    }
)

print(weapon.data.name)                  # Example Rifle
print(weapon.data.entry.type)            # primary
print(weapon.data.entry.ammo.reload_time)
print(weapon.mode.stats.crit_chance)
```

Weapon-wide fields belong directly to the named entry. Attack-specific fields
belong inside each attack's `stats` mapping.

### Multiple attacks and related child attacks

```python
from warframe_damage_calculator import Primary

weapon = Primary(
    {
        "Example Launcher": {
            "type": "primary",
            "subtype": "rifle",
            "ammo": {
                "reload_time": 2.5,
                "magazine_size": 6,
            },
            "attacks": {
                "projectile": {
                    "trigger": "semi",
                    "delivery": "projectile",
                    "children": ["explosion"],
                    "stats": {
                        "damage": {"impact": 100},
                        "crit_chance": 0.20,
                        "crit_damage": 2.0,
                        "status_chance": 0.20,
                        "fire_rate": 1.0,
                    },
                },
                "explosion": {
                    "trigger": "semi",
                    "delivery": "projectile",
                    "aoe": True,
                    "stats": {
                        "damage": {"blast": 500},
                        "forced_procs": {"impact": 1},
                        "crit_chance": 0.20,
                        "crit_damage": 2.0,
                        "status_chance": 0.20,
                        "fire_rate": 1.0,
                    },
                },
            },
        }
    }
)

weapon.set_mode("Projectile")

print(weapon.stats.parent.effective.damage)
print(weapon.stats.child[0].effective.damage)
print(weapon.stats.average.total_dps)
```

For ranged weapons, selected attacks may name child attacks through `children`.
Their complete calculations are exposed through
`weapon.stats.child`, including each child's base, modded,
effective, average, and descendant states.

### Constructing a melee weapon

```python
from warframe_damage_calculator import Melee

weapon = Melee(
    {
        "Example Sword": {
            "type": "melee",
            "subtype": "sword",
            "attacks": {
                "normal_attack": {
                    "trigger": "melee",
                    "delivery": "melee",
                    "stats": {
                        "damage": {
                            "impact": 10,
                            "puncture": 10,
                            "slash": 80,
                        },
                        "crit_chance": 0.20,
                        "crit_damage": 2.0,
                        "status_chance": 0.30,
                        "fire_rate": 1.0,
                    },
                }
            },
        }
    }
)

print(weapon.stats.parent.base.attack_speed)
print(weapon.stats.average.total_dps)
```

For melee attacks, the selected attack's `fire_rate` is used as the base attack
speed.

### Constructing an upgrade

```python
from warframe_damage_calculator import Upgrade

upgrade = Upgrade(
    {
        "Example Mod": {
            "type": "mod",
            "max_rank": 10,
            "compatibility": {
                "types": ["primary"],
                "subtypes": ["rifle"],
                "exilus": False,
            },
            "incompatibility": ["Conflicting Mod"],
            "stats": {
                "base_damage": 1.65,
                "crit_chance": 2.0,
                "fire_rate": -0.20,
                "heat": 0.90,
            },
        }
    }
)

print(upgrade.data.name)
print(upgrade.data.entry.stats.base_damage)
print(upgrade.stats.total.base_damage)
```

The canonical entry contains persistent metadata and stat effects. Runtime
values are stored separately in `upgrade.data.runtime`.

### Upgrade effect forms

A stat may be a scalar, one effect record, or a list containing any mixture of
the two:

```python
from warframe_damage_calculator import Build, Upgrade

upgrade = Upgrade(
    {
        "Example Arcane": {
            "type": "arcane",
            "max_rank": 5,
            "stats": {
                "base_damage": [
                    0.30,
                    {"value": 0.20, "when": "headshot"},
                    {"value": 0.10, "stacks": {"when": "kill", "max": 3}},
                    {"value": 0.25, "rank": 5},
                    {"value": 0.15, "equipped": ["Partner"]},
                ]
            },
        }
    }
)

partner = Upgrade({"Partner": {"type": "buff", "stats": {}}})

upgrade.data.runtime.update(
    {
        "rank": 5,
        "headshot": True,
        "kill": 2,
    }
)

build = Build(upgrade, partner)
resolved = build.upgrades[0]

print(resolved.stats.static.base_damage)       # 0.30
print(resolved.stats.conditional.base_damage)  # 0.20
print(resolved.stats.stacking.base_damage)     # 0.20
print(resolved.stats.rank_locked.base_damage)  # 0.25
print(resolved.stats.modular.base_damage)      # 0.15
print(resolved.stats.total.base_damage)        # 1.10
```

| Form | Example | Behavior |
|---|---|---|
| Scalar | `"base_damage": 1.65` | Always active. |
| Static record | `{"value": 1.65}` | Always active. |
| Conditional | `{"value": 0.3, "when": "headshot"}` | Active when the named runtime condition is truthy. |
| Stacking | `{"value": 0.1, "stacks": {"when": "kill", "max": 3}}` | Multiplied by the named stack count. |
| Rank-locked | `{"value": 0.3, "rank": 5}` | Added at full value when the current rank reaches 5. |
| Equipped | `{"value": 0.55, "equipped": ["Partner"]}` | Active when every named upgrade is equipped. |
| Mixed list | `[1.0, {...}, {...}]` | Resolves each effect independently. |

Boolean effects aggregate with logical OR. Numeric effects add together.
Damage-type effects aggregate into a single ordered damage distribution.

### Runtime rank, conditions, and stacks

The loader accepts runtime overrides through `context`:

```python
inactive = arsenal.get("Galvanized Hell", context={"stacks": 0})
active = arsenal.get("Galvanized Hell", context={"stacks": 4})
partial_rank = arsenal.get("Serration", context={"rank": 4})
```

For a manually constructed upgrade:

```python
upgrade.data.runtime.rank = 5
upgrade.data.runtime.kill = 3
upgrade.data.runtime.headshot = True
upgrade.stats.resolve()
```

Ranks are zero-based. Ordinary effects scale by:

```text
(rank + 1) / (max_rank + 1)
```

Omitted ranks default to `max_rank`. Omitted stack counts generally resolve to
the effect's maximum for an untouched database upgrade. Supplying runtime
context lets callers explicitly disable or limit those values.

An upgrade containing a rank-locked effect currently skips proportional scaling
for its other effects. This matches the database representation used by the
current resolver.

### Copying upgrades

```python
copied = upgrade.copy()
```

`Upgrade.copy()` creates a detached upgrade, preserves its runtime values, and
resolves the copied stats. `Build` uses this method whenever it accepts or
iterates over upgrades.

---

## Builds

```python
from warframe_damage_calculator import Build, arsenal

serration = arsenal.get("Serration")
critical_delay = arsenal.get("Critical Delay")

base_build = Build(serration)
crit_build = base_build + critical_delay
restored_build = crit_build - critical_delay
copied_build = crit_build.copy()

print(len(base_build))       # 1
print(len(crit_build))       # 2
print(len(restored_build))   # 1
```

`Build` is iterable and supports non-mutating addition and subtraction.
Subtraction matches upgrades by case-insensitive name.

A build owns detached copies of its upgrades. Iterating over a build also yields
copies. The canonical mutable collection is `build.upgrades`:

```python
build.upgrades[0].data.runtime.stacks = 0
build.stats.resolve()
```

`weapon.configure(build)` copies the build again, so later changes to the
original build do not silently modify the configured weapon.

---

## Database Loader

The package-level database entry point is `arsenal`.

### Named lookups

```python
from warframe_damage_calculator import Melee, Primary, Secondary, Upgrade, arsenal

primary = arsenal.get("Corinth Prime")
secondary = arsenal.get("Kuva Nukor")
melee = arsenal.get("Prisma Skana")
upgrade = arsenal.get("Critical Delay")

assert isinstance(primary, Primary)
assert isinstance(secondary, Secondary)
assert isinstance(melee, Melee)
assert isinstance(upgrade, Upgrade)
```

Names are normalized by trimming whitespace, collapsing repeated whitespace,
and ignoring case. Missing names return `None`.

Every lookup returns a fresh model. Mutating one result does not modify the
canonical database or a later lookup.

Exact bundled name literals are typed by category, allowing editors and type
checkers to infer `Primary`, `Secondary`, `Melee`, or `Upgrade` directly.

### Listing and filtering

When `name` is omitted, `get()` returns a dictionary keyed by item name:

```python
all_items = arsenal.get()
weapons = arsenal.get(type="weapon")
upgrades = arsenal.get(type="upgrade")
mods = arsenal.get(type="mod")
arcanes = arsenal.get(type="arcane")
primaries_and_compatible_upgrades = arsenal.get(type="primary")
shotguns_and_compatible_upgrades = arsenal.get(type="shotgun")
```

Category filters such as `weapon`, `upgrade`, `mod`, and `arcane` return only
that database category. Weapon-family filters such as `primary`, `secondary`,
`melee`, `rifle`, `shotgun`, `bow`, `sniper`, and `pistol` may return both
weapons and upgrades compatible with that family.

Common plural aliases such as `weapons`, `mods`, and `arcanes` are accepted.

### Attribute-only queries

```python
weapon_names = arsenal.get(type="weapon", attribute="name")
base_crit = arsenal.get("Corinth Prime", attribute="crit_chance")
weapon_crits = arsenal.get(type="weapon", attribute="crit_chance")
shotgun_subtypes = arsenal.get(type="shotgun", attribute="subtype")
```

`attribute="name"` returns a sorted list when no item name is supplied. Other
attributes return one extracted value or a dictionary of values.

For weapons, attribute lookup checks the canonical entry, ammo data, calculated
base and effective states, the selected attack, and its stats. For upgrades, it
checks runtime values and canonical upgrade stats.

### Custom databases

```python
from warframe_damage_calculator.loader.loader import WarframeDatabase

custom = WarframeDatabase.from_file("data/database.json")

# Equivalent when the folder contains database.json:
custom = WarframeDatabase.from_folder("data")
```

The file uses the same top-level schema as the bundled database:

```json
{
  "schema_version": 1,
  "weapons": {},
  "upgrades": {},
  "riven_stats": {}
}
```

Raw Riven stat ranges remain available through the database object:

```python
rifle_riven_stats = arsenal.riven_stats["rifle"]
print(rifle_riven_stats["crit_chance"])
```

---

## Model Data Layout

### Weapon data

```python
weapon.data.name
weapon.data.entry
weapon.data.entry.type
weapon.data.entry.subtype
weapon.data.entry.disposition
weapon.data.entry.ammo
weapon.data.entry.attacks
weapon.data.entry.evolutions
weapon.mode
weapon.mode.stats
```

`weapon.data` contains one named entry. `weapon.data.entry` is a convenience
property for that entry, and `weapon.mode` points to the currently selected
attack.

### Upgrade data

```python
upgrade.data.name
upgrade.data.entry
upgrade.data.entry.type
upgrade.data.entry.max_rank
upgrade.data.entry.compatibility
upgrade.data.entry.incompatibility
upgrade.data.entry.stats
upgrade.data.runtime
```

Permanent database data and runtime resolution values are intentionally
separate.

### Sparse typed data

Nested mappings are converted to typed `Data` subclasses and support both
mapping and attribute access:

```python
print(weapon.data.entry.ammo.magazine_size)
print(weapon.mode.stats.crit_chance)

weapon.mode.stats.crit_chance = 0.40
```

Defaults are readable without appearing in normal iteration:

```python
stats = weapon.mode.stats
print(stats.multishot)  # default: 1.0
print(dict(stats))      # only explicitly stored fields
```

Use `with_defaults()` for a detached dense dictionary and `copy()` for a deep
copy:

```python
snapshot = weapon.mode.stats.with_defaults()
copied_data = weapon.data.copy()
```

### Damage distributions

Damage and forced-proc fields are converted to `Dist` objects:

```python
damage = weapon.stats.parent.effective.damage

print(damage.total_damage())
print(damage.weight("slash"))
print(dict(damage.include(["slash", "heat"])))
print(dict(damage.exclude(["impact", "puncture"])))
print(dict(damage.positive()))
print(dict(damage.sorted()))
```

Distributions support addition, scalar multiplication, modifier application,
and elemental combination:

```python
combined = damage.combine()
doubled = damage * 2
merged = damage + combined
```

---

## Weapon Entry Reference

### Weapon-wide fields

| Field | Default | Meaning |
|---|---:|---|
| `type` | `None` | `primary`, `secondary`, `melee`, or a supported database category such as `archgun`. |
| `subtype` | `None` | Weapon family such as `rifle`, `shotgun`, `bow`, `pistol`, or a melee class. |
| `disposition` | `0.0` | Riven disposition metadata. |
| `ammo` | empty | Global reload, magazine, battery, and Incarnon ammo data. |
| `attacks` | empty | Named attack definitions. The first attack is the default mode. |
| `evolutions` | empty | Incarnon evolution tiers and perks. |

Common ranged ammo fields:

| Field | Default | Meaning |
|---|---:|---|
| `reload_time` | `0.0` | Base reload duration in seconds. |
| `magazine_size` | `1` | Base magazine size. |
| `recharge_rate` | `0.0` | Battery recharge units per second. |
| `recharge_delay` | absent | Marks a battery weapon and preserves its delay metadata. |
| `incarnon_charges` | `0` | Incarnon charge capacity metadata. |
| `incarnon_recharge_count` | `0` | Incarnon recharge-count metadata. |

### Attack fields

| Field | Default | Meaning |
|---|---:|---|
| `trigger` | `None` | Trigger class such as `semi`, `auto`, `charge`, or `melee`. |
| `delivery` | `None` | Delivery class such as `hitscan`, `projectile`, `beam`, or `melee`. |
| `aoe` | `False` | Whether the attack is radial or area-of-effect. |
| `children` | empty | Related attacks calculated with the selected ranged attack. |
| `stats` | empty | Attack-specific combat stats. |

Common attack stats:

| Field | Default | Meaning |
|---|---:|---|
| `ammo_cost` | `1` | Attack ammo-cost metadata; not currently applied to fire-cycle math. |
| `punch_through` | `0.0` | Punch-through metadata. |
| `damage` | empty | Damage distribution. |
| `forced_procs` | empty | Guaranteed proc counts by damage or status type. |
| `falloff` | empty | Falloff metadata; currently stored but not applied to calculations. |
| `crit_chance` | `0.0` | Base critical chance. |
| `crit_damage` | `1.0` | Base critical multiplier. |
| `status_chance` | `0.0` | Base status chance per projectile. |
| `multishot` | `1.0` | Native projectiles per attack. |
| `fire_rate` | `0.05` | Attacks per second, or melee attack speed. |
| `burst_count` | `1` | Attacks in each burst. |
| `burst_delay` | `0.0` | Delay between burst attacks. |
| `charge_time` | `0.0` | Charge duration. |
| `co_factor` | `1.0` | Attack-specific Condition Overload factor. |
| `co_effect` | `"adds"` | Whether Condition Overload adds to or multiplies base damage. |

---

## Reading Calculated Results

Each weapon exposes:

| Attribute | Description |
|---|---|
| `weapon.data` | Canonical named weapon entry. |
| `weapon.mode` | Selected attack. |
| `weapon.evolutions` | Selected Incarnon perks. |
| `weapon.build` | Detached active build. |
| `weapon.stats` | Calculator and calculated states. |
| `weapon.format` | Text formatter. |

### Weapon state buckets

| Bucket | Description |
|---|---|
| `weapon.stats.parent` | Complete calculation bucket for the selected attack. |
| `weapon.stats.parent.base` | Dense normalized stats for the selected attack. |
| `weapon.stats.parent.modded` | Intermediate additive, multiplicative, and locked values. |
| `weapon.stats.parent.effective` | Final stats used by expected-value calculations. |
| `weapon.stats.parent.average` | Expected values for the selected attack by itself. |
| `weapon.stats.child` | Related attack buckets calculated with the selected attack. |
| `weapon.stats.average` | Combined parent-and-descendant DPH, DoT, and DPS using the parent's attack rate. |

Each item in `weapon.stats.child` is calculated through the same
base, modded, effective, and average pipeline.

```python
average = weapon.stats.average

print(average.crit_chance)
print(average.crit_multiplier)
print(average.flat_dph)
print(average.flat_dotph)
print(average.total_dph)
print(average.flat_dps)
print(average.flat_dotps)
print(average.total_dps)
```

Ranged models also expose weakpoint versions, effective fire rate, expected
procs per shot, and beam behavior:

```python
print(average.fire_rate)
print(average.procs_per_shot)
print(average.weakpoint_crit_chance)
print(average.total_weakpoint_dph)
print(average.total_weakpoint_dps)
```

Mechanic-specific outputs include:

| Model | Output |
|---|---|
| Primary | `primed_chamber_multiplier` |
| Secondary | `secondary_enervate_bonus`, `weakpoint_secondary_enervate_bonus` |
| Melee | `melee_duplicate_multiplier`, `melee_doughty_bonus` |

### Upgrade and build buckets

Both upgrade and build calculators expose:

```python
upgrade.stats.static
upgrade.stats.conditional
upgrade.stats.modular
upgrade.stats.stacking
upgrade.stats.rank_locked
upgrade.stats.total

build.stats.static
build.stats.conditional
build.stats.modular
build.stats.stacking
build.stats.rank_locked
build.stats.total
```

### Contribution estimates

```python
weapon = arsenal.get("Acceltra Prime").configure(
    Build(
        arsenal.get("Serration"),
        arsenal.get("Critical Delay"),
    )
)

print(weapon.stats.contribution_values())
print(weapon.stats.contribution_proportions())
print(weapon.format.upgrades())
```

Each contribution is the full build's DPS minus the DPS after removing that
upgrade. These are marginal estimates, so interactions between upgrades mean
the proportions are not independent multipliers.

### Formatters

```python
print(weapon.format.summary())
print(weapon.format.upgrades())
```

Ranged summaries include the selected attack, global fire-cycle stats, direct
and related attack damage, weakpoint values, expected procs, DPH, DoT, and DPS.
Melee summaries include attack speed and expected damage for the selected
attack.

---

## Supported Upgrade Stats

Unknown fields can be stored and resolved, but only fields consumed by a weapon
calculator change calculated results.

### Damage and faction stats

- Damage types: `impact`, `puncture`, `slash`, `cold`, `electricity`, `heat`,
  `toxin`, `blast`, `corrosive`, `gas`, `magnetic`, `radiation`, `viral`,
  `void`, and `tau`
- `damage`
- `base_damage`
- `multiplicative_base_damage`
- `condition_overload`
- `corpus_damage`
- `grineer_damage`
- `infested_damage`
- `murmur_damage`
- `orokin_damage`
- `sentient_damage`
- `weakpoint_damage`
- `multishot`
- `multishot_lock`

When multiple faction stats are present, the calculator uses the largest one.
Faction damage is applied twice to modeled DoT damage.

### Fire control

- `attack_speed`
- `fire_rate`
- `multiplicative_fire_rate`
- `fire_rate_lock`
- `reload_speed`
- `magazine_capacity`
- `ammo_efficiency`

### Critical

- `crit_chance`
- `flat_crit_chance`
- `multiplicative_crit_chance`
- `weakpoint_crit_chance`
- `multiplicative_weakpoint_crit_chance`
- `crit_damage`
- `flat_crit_damage`

### Status and special mechanics

- `status_chance`
- `status_damage`
- `hunter_munitions`
- `internal_bleeding`
- `primed_chamber`
- `vigilante_bonus`
- `secondary_enervate`
- `secondary_encumber`
- `melee_duplicate`
- `melee_doughty`

`elements` is preserved by the resolver but is not read directly by the weapon
calculator. Use individual damage-type fields or `damage` to modify the damage
distribution.

`melee_doughty` exposes `weapon.stats.average.melee_doughty_bonus`; that bonus is
not yet applied to DPH or DPS.

---

## Calculation Scope and Assumptions

The library computes long-run expected values rather than simulating individual
shots, projectiles, or animation frames.

### Damage, critical hits, status, and DoT

- Elemental combination follows the order in which elemental upgrade effects are aggregated.
- DoT values represent expected total proc damage using a multiplier of `2.1` for Slash and `3.0` for Heat, Toxin, Electricity, and Gas.
- Native status chance is treated per projectile.
- Forced proc counts are added independently of ordinary status weighting.
- Faction damage is applied twice to modeled DoT.
- Related ranged attacks are included automatically when the selected attack lists them as children.
- Falloff, punch through, and several other database fields are currently metadata only.

### Condition Overload

- Condition Overload counts unique damage types plus positive forced-proc types on the attack.
- The effect may be capped by the upgrade's structured `max_stacks` value.
- Each attack may scale the bonus with `co_factor`.
- `co_effect="adds"` adds the bonus to additive base damage.
- `co_effect="multiplies"` adds the bonus to multiplicative base damage.
- Child attacks resolve their own Condition Overload factor and effect.

### Primary mechanics

- Hunter Munitions is modeled as an expected Slash proc chance on critical hits.
- Internal Bleeding doubles its modeled chance below `2.5` effective fire rate.
- Primed Chamber is averaged across the magazine and also affects modeled DoT from the boosted attack.
- Vigilante bonus is represented as an expected critical-tier bonus capped at `0.30`.

### Secondary mechanics

- Secondary Encumber is modeled as triggering at most once per attack.
- Its chance accounts for status chance and multishot.
- It contributes expected DoT and may add an Impact source for Internal Bleeding or Hemorrhage.
- Secondary Enervate uses an expected-state calculation and exposes separate normal-hit and weakpoint bonuses.

### Fire cycle

- Charge time and burst timing are included in average fire rate.
- Condition Overload uses the expected number of distinct status types acquired over a five-second firing window.
- `fire_rate_lock` ignores additive and multiplicative fire-rate upgrades.
- `multishot_lock` preserves native multishot but ignores upgrade multishot.
- Beam weapons apply beam-specific ammo-efficiency and DoT multishot behavior.
- Battery recharge time is based on magazine capacity and recharge rate.
- Magazine capacity uses Warframe-style true rounding and never falls below one.
- Average fire rate is a closed-form fire-cycle calculation, not a frame-by-frame simulation.

### Melee

Melee DPS is calculated as expected damage per selected attack multiplied by its
attack speed. Stance animation timing, combo counters, follow-through, range,
and multi-hit stance sequences are not modeled, so melee DPS is best treated as
a relative comparison.

---

## Current Limitations

The calculator does not currently model:

- Enemy armor, shields, health types, resistances, or damage attenuation
- Time-to-kill
- Most non-DoT status effects
- Projectile travel time or falloff application
- Headshot eligibility or enemy-specific weakpoint rules
- Melee stance animation timing and combo progression
- Heavy-attack wind-up, slam timing, and multi-hit sequences as complete gameplay cycles
- Frame abilities and weapon-specific scripted mechanics unless represented by upgrade stats
- Loadout legality, duplicate slots, Exilus restrictions, or incompatibility enforcement

Compatibility and incompatibility fields are metadata. Applications using the
library must enforce legal loadouts themselves.

---

## Contributing

Bug reports, feature requests, database corrections, and pull requests are
welcome.

## License

Released under the MIT License.
