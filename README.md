# Warframe Damage Calculator

> Deterministic, expected-value damage calculations for Warframe weapons.

**Warframe Damage Calculator** is a Python library for comparing weapon builds
without Monte Carlo simulation. It combines a weapon definition with mods,
arcanes, buffs, and other upgrades, then calculates the long-run average damage
of each attack and the average DPS of the complete fire cycle.

The project is currently **alpha software**. It is useful for theorycrafting,
build comparison, testing custom mechanics, and powering external tools, but it
is not a complete simulation of Warframe combat.

---

## Features

### Weapon and damage modeling

- Primary, Secondary, and Melee weapon models
- Direct-hit and radial explosion damage
- Physical, elemental, combined elemental, Void, and Tau damage
- Ordered elemental combination
- Critical chance, critical damage, status chance, and forced procs
- Weakpoint damage and weakpoint critical chance
- Expected flat damage, DoT damage, DPH, and DPS
- Native multishot and modded multishot
- Beam, battery, burst-fire, charge-weapon, magazine, reload, and ammo-efficiency calculations
- Fire-rate and multishot locks

### Upgrade resolution

- Static effects
- Conditional effects
- Stacking effects with independent stack conditions
- Proportional rank scaling
- Rank-locked effects
- Effects that require another equipped upgrade
- Automatic weapon-category conditions such as `primary`, `shotgun`, or `bow`
- Separate `static`, `conditional`, `modular`, `stacking`, `rank_locked`, and `total` result buckets

### Special mechanics

- Hunter Munitions
- Internal Bleeding and Hemorrhage
- Primed Chamber
- Vigilante set bonus
- Secondary Enervate
- Secondary Encumber
- Melee Duplicate
- Melee Doughty bonus calculation
- Sacrificial set equipped bonuses

### Data and API

- Bundled weapon, mod, and arcane database
- Normalized name lookup
- Weapon, upgrade, compatibility, and trigger filters
- Attribute-only database queries
- Custom database files and folders
- Build composition with `+` and `-`
- Upgrade contribution estimates
- Human-readable ranged and melee summaries
- Typed, sparse, mutable model data with attribute access and detached copies
- Damage-distribution helpers for totals, weights, filtering, arithmetic, and combination

Not currently modeled: enemy defenses, armor, health types, damage attenuation,
time-to-kill, non-DoT status effects, projectile falloff, headshot eligibility,
melee stance timing, combo counters, heavy attacks, slam attacks, and
frame-by-frame firing behavior.

---

## Requirements

- Python **3.14+**

---

## Installation

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

upgrades = [
    arsenal.get("Galvanized Hell", context={"kill": 4}),
    arsenal.get("Primed Chilling Grasp"),
    arsenal.get("Critical Deceleration"),
]
assert all(isinstance(upgrade, Upgrade) for upgrade in upgrades)

weapon.configure(Build(*upgrades))

print(weapon.format.summary())
print(f"Average DPS: {weapon.stats.average.total_dps:.2f}")
print(f"Weakpoint DPS: {weapon.stats.average.total_weakpoint_dps:.2f}")
```

Database upgrades resolve at maximum rank by default. Runtime conditions and
stack counts are passed through `context`; here, Galvanized Hell is evaluated at
four kill stacks.

For a larger shotgun build, see `examples/corinth_prime.py`.

---

## More Examples

### Primary build with stacking effects

```python
from warframe_damage_calculator import Build, Primary, Upgrade, arsenal

weapon = arsenal.get("Corinth Prime")
galvanized_hell = arsenal.get("Galvanized Hell", context={"kill": 4})
merciless = arsenal.get("Primary Merciless", context={"kill": 12})
hunter_munitions = arsenal.get("Hunter Munitions")
critical_delay = arsenal.get("Critical Deceleration")

assert isinstance(weapon, Primary)
assert all(
    isinstance(item, Upgrade)
    for item in (galvanized_hell, merciless, hunter_munitions, critical_delay)
)

build = Build(
    galvanized_hell,
    merciless,
    hunter_munitions,
    critical_delay,
)
weapon.configure(build)

print("Resolved build stats:")
print(weapon.build.stats.total)
print()
print(weapon.format.summary())
```

The build resolver evaluates each upgrade against both the weapon and the other
upgrades in the build. This activates automatic type conditions, manual runtime
conditions, stack counts, rank locks, and equipped-set effects before the weapon
is recalculated.

### Secondary special mechanics

```python
from warframe_damage_calculator import Build, Secondary, Upgrade, arsenal

weapon = arsenal.get("Kuva Nukor")
encumber = arsenal.get("Secondary Encumber")

assert isinstance(weapon, Secondary)
assert isinstance(encumber, Upgrade)

weapon.configure(Build(encumber))

average = weapon.stats.average
print(f"Expected procs per attack: {average.procs_per_shot:.2f}")
print(f"Expected DoT per attack:   {average.flat_dotph:.2f}")
print(f"Total DPS:                 {average.total_dps:.2f}")
```

Secondary Enervate is configured in the same way. Its per-hit critical-chance
state and reset behavior are handled automatically:

```python
enervate = arsenal.get("Secondary Enervate")
assert isinstance(enervate, Upgrade)
weapon.configure(enervate)

print(weapon.stats.average.secondary_enervate_bonus)
print(weapon.stats.average.weakpoint_secondary_enervate_bonus)
```

### Melee build and equipped-set bonuses

```python
from warframe_damage_calculator import Build, Melee, Upgrade, arsenal

weapon = arsenal.get("Prisma Skana")
pressure = arsenal.get("Sacrificial Pressure")
steel = arsenal.get("Sacrificial Steel")
duplicate = arsenal.get("Melee Duplicate")

assert isinstance(weapon, Melee)
assert all(isinstance(item, Upgrade) for item in (pressure, steel, duplicate))

weapon.configure(Build(pressure, steel, duplicate))

print(weapon.build.stats.modular)
print(f"Duplicate multiplier: {weapon.stats.average.melee_duplicate_multiplier:.3f}x")
print(weapon.format.summary())
```

Sacrificial Pressure and Sacrificial Steel detect each other through their
`when_equipped` effects.

### Build composition and comparison

`Build` objects are iterable, have a length, and support non-mutating addition
and subtraction:

```python
from warframe_damage_calculator import Build, Upgrade, arsenal

serration = arsenal.get("Serration")
critical_delay = arsenal.get("Critical Delay")
assert isinstance(serration, Upgrade)
assert isinstance(critical_delay, Upgrade)

base_build = Build(serration)
crit_build = base_build + critical_delay
restored_build = crit_build - critical_delay

print(len(base_build))       # 1
print(len(crit_build))       # 2
print(len(restored_build))   # 1

for upgrade in crit_build:
    print(upgrade.data.context.name)
```

A build copies each upgrade's data when it is created, so later mutations to the
original `Upgrade` do not silently change an existing build.

### Upgrade contribution estimates

```python
from warframe_damage_calculator import Build, Primary, Upgrade, arsenal

weapon = arsenal.get("Acceltra Prime")
serration = arsenal.get("Serration")
critical_delay = arsenal.get("Critical Delay")

assert isinstance(weapon, Primary)
assert isinstance(serration, Upgrade)
assert isinstance(critical_delay, Upgrade)

weapon.configure(Build(serration, critical_delay))

print(weapon.stats.contribution_values())
print(weapon.stats.contribution_proportions())
print(weapon.format.upgrades())
```

A contribution is calculated by removing one upgrade, recomputing the weapon,
and subtracting the reduced build's DPS from the full build's DPS. These are
marginal estimates: interactions between upgrades mean the proportions are not
independent multipliers and do not necessarily add intuitive value in every
build.

### Creating a weapon and upgrade manually

Weapon and upgrade constructors accept nested mappings with `stats` and
`context` sections:

```python
from warframe_damage_calculator import Primary, Upgrade

weapon = Primary(
    {
        "stats": {
            "damage": {
                "impact": 20,
                "puncture": 30,
                "slash": 50,
            },
            "forced_procs": {"slash": 1},
            "explosion_damage": {"heat": 100},
            "explosion_forced_procs": {"heat": 1},
            "crit_chance": 0.30,
            "crit_damage": 2.2,
            "status_chance": 0.25,
            "multishot": 1,
            "fire_rate": 3.0,
            "reload_speed": 2.0,
            "magazine_capacity": 20,
            "burst_count": 1,
            "burst_delay": 0.0,
            "charge_time": 0.0,
            "recharge_rate": 0.0,
            "weakpoint_damage": 3.0,
        },
        "context": {
            "name": "Example Weapon",
            "type": "rifle",
            "trigger": "semi",
            "is_beam": False,
            "is_battery": False,
        },
    }
)

upgrade = Upgrade(
    {
        "stats": {
            "base_damage": 1.65,
            "crit_chance": 2.0,
            "fire_rate": -0.2,
            "heat": 0.9,
        },
        "context": {
            "name": "Example Mod",
            "type": "mod",
        },
    }
)

weapon.configure(upgrade)
print(weapon.format.summary())
```

Ranged `reload_speed` values represent reload time in seconds despite the field
name. Upgrade `reload_speed` values are additive reload-speed modifiers.

### One upgrade with every effect form

A stat may contain one effect or a list of effects:

```python
from warframe_damage_calculator import Build, Upgrade

upgrade = Upgrade(
    {
        "stats": {
            "base_damage": [
                0.30,
                {"value": 0.20, "when": "headshot"},
                {"value": 0.10, "stacks_on": "kill"},
                {"value": 0.25, "at_rank": 5},
                {"value": 0.15, "when_equipped": "Partner"},
            ],
        },
        "context": {
            "name": "Example Arcane",
            "max_rank": 5,
            "rank": 5,
            "max_stacks": 3,
            "headshot": True,
            "kill": 2,
        },
    }
)
partner = Upgrade({"context": {"name": "Partner"}})
upgrade.stats.resolve(build=Build(upgrade, partner))

print(upgrade.stats.static.base_damage)       # 0.30
print(upgrade.stats.conditional.base_damage)  # 0.20
print(upgrade.stats.modular.base_damage)      # 0.15
print(upgrade.stats.stacking.base_damage)     # 0.20
print(upgrade.stats.rank_locked.base_damage)  # 0.25
print(upgrade.stats.total.base_damage)        # 1.10
```

### Changing runtime conditions

The simplest approach is to request a fresh database copy with new context:

```python
inactive = arsenal.get("Galvanized Hell", context={"kill": 0})
active = arsenal.get("Galvanized Hell", context={"kill": 4})
```

For a manually created upgrade, update its context and resolve it again:

```python
upgrade.data.context.kill = 3
upgrade.stats.resolve()
print(upgrade.stats.total)
```

When an upgrade is already inside a build, create a new `Build` from the updated
upgrade or modify `build.data.upgrades` deliberately and call
`build.stats.resolve()`. Calling `weapon.configure(build)` or
`weapon.stats.recompute()` then refreshes the weapon outputs.

---

## Public API

The package root exports:

```python
from warframe_damage_calculator import (
    Upgrade,
    Build,
    Melee,
    Primary,
    Secondary,
    arsenal,
)
```

| Object | Purpose |
|---|---|
| `Upgrade` | One mod, arcane, buff, set bonus, or other stat modifier. |
| `Build` | A copied collection of upgrades with resolved aggregate stats. |
| `Primary` | Primary ranged-weapon model. |
| `Secondary` | Secondary ranged-weapon model. |
| `Melee` | Melee light-attack model. |
| `arsenal` | Bundled weapon and upgrade database. |

`Data` and `Dist` are implementation types rather than package-root exports.
They are still visible through public model attributes such as `weapon.data`,
`weapon.stats.effective`, and `weapon.stats.effective.damage`.

A typical workflow is:

1. Load or create a weapon.
2. Load or create upgrades.
3. Set their rank, conditions, and stacks.
4. Create a `Build`, or pass upgrades directly to the weapon.
5. Read calculated values from `weapon.stats` or formatted text from
   `weapon.format`.

`configure()` returns the weapon, so chaining is supported:

```python
weapon = Primary({...}).configure(upgrade_1, upgrade_2)
```

It accepts exactly one `Build`, any number of `Upgrade` objects, or no arguments
to clear the build. Mixing a `Build` and individual upgrades in the same call
raises `TypeError`.

---

## Database Loader

The bundled database entry point is `arsenal.get()`.

### Named lookups

```python
weapon = arsenal.get("Acceltra Prime")
mod = arsenal.get("Critical Delay")
ranked_mod = arsenal.get("Critical Delay", context={"rank": 3})
base_crit = arsenal.get("Acceltra Prime", attribute="crit_chance")
```

Names are normalized for lookup by trimming whitespace, collapsing repeated
whitespace, and ignoring case. A missing name, or a name rejected by the optional `type` filter,
returns `None`.

Exact bundled name literals are typed by database category, so editors infer
`Primary`, `Secondary`, `Melee`, or `Upgrade` directly. Dynamic strings and
custom `WarframeDatabase` instances retain the general union return type.

`context` is merged into a fresh copy of the database entry, so separate calls
do not modify the bundled data.

### Listing entries

When `name` is omitted, `get()` returns a dictionary keyed by item name:

```python
all_items = arsenal.get()
weapons = arsenal.get(type="weapon")
mods = arsenal.get(type="mod")
arcanes = arsenal.get(type="arcane")
weapon_names = arsenal.get(type="weapon", attribute="name")
```

`attribute="name"` returns a sorted list of names without constructing every
model. Other attributes return a dictionary of extracted values:

```python
weapon_crits = arsenal.get(type="weapon", attribute="crit_chance")
shotgun_triggers = arsenal.get(type="shotgun", attribute="trigger")
```

### Type filters

The `type` argument is a broad, single matcher rather than a composable query:

- `weapon`, `upgrade`, `mod`, and `arcane` select database categories.
- `primary`, `secondary`, and `melee` match weapons in that category **and**
  upgrades compatible with it.
- `rifle`, `shotgun`, `bow`, `sniper`, and `pistol` match relevant weapons and
  compatible upgrades.
- Trigger names such as `semi` match weapons with that trigger and upgrades
  whose requirements reference it.
- Common plurals such as `weapons`, `mods`, and `arcanes` are accepted.

For example, `arsenal.get(type="shotgun")` contains shotgun weapons as well as
shotgun-compatible mods and arcanes. Use `type="weapon"`, `type="mod"`, or
`type="arcane"` when only one database category is wanted.

The loader does not currently combine filters such as “shotgun weapons only” in
one call.

### Custom databases

Advanced callers can construct a database from their own JSON files:

```python
from warframe_damage_calculator.data.loader import WarframeDatabase

custom = WarframeDatabase.from_files(
    "data/weapons.json",
    "data/upgrades.json",
)

# Equivalent folder layout:
# data/weapons.json
# data/upgrades.json
custom = WarframeDatabase.from_folder("data")
```

The custom files use the same grouped schema as the bundled database.

---

## Model Data

Every model exposes its input data publicly:

```python
weapon.data.stats
weapon.data.context
upgrade.data.stats
upgrade.data.context
build.data.upgrades
build.data.context
```

Nested mappings are converted to typed data objects, so fields support both
mapping and attribute access:

```python
print(weapon.data.stats.crit_chance)
print(weapon.data.context.name)

weapon.data.stats.crit_chance = 0.40
weapon.data.context.is_beam = True
```

### Sparse defaults

Typed data remains sparse. Defaults are readable without being inserted into
normal iteration:

```python
weapon = Primary()

print(weapon.data.stats.multishot)  # 1.0
print(dict(weapon.data.stats))      # {}
```

Use `with_defaults()` for a detached, dense snapshot:

```python
snapshot = weapon.data.stats.with_defaults()
snapshot["crit_chance"] = 2

# The original model is unchanged.
print(weapon.data.stats.crit_chance)  # 0
```

`copy()` performs a deep copy, including nested data, lists, and damage
distributions. Mapping unions preserve the typed data subclass:

```python
copied = weapon.data.copy()
updated = weapon.data | {"context": {"name": "Copy"}}
```

### Damage-distribution helpers

Calculated damage fields expose distribution methods without requiring a
package-root `Dist` import:

```python
damage = weapon.stats.effective.damage

print(damage.total_damage())
print(damage.weight("slash"))
print(dict(damage.include(["slash", "heat"])))
print(dict(damage.exclude(["impact", "puncture"])))
print(dict(damage.positive()))
print(dict(damage.sorted()))
```

Distributions also support addition, scalar multiplication, elemental
combination, and application of a modifier distribution:

```python
combined = damage.combine()
doubled = damage * 2
merged = damage + combined
```

---

## Weapon Input Fields

### Shared fields

| Field | Default | Meaning |
|---|---:|---|
| `damage` | empty | Direct-hit damage distribution. |
| `forced_procs` | empty | Guaranteed direct-hit proc counts by damage type. |
| `crit_chance` | `0.0` | Base critical chance. |
| `crit_damage` | `1.0` | Base critical multiplier. |
| `status_chance` | `0.0` | Base status chance per projectile. |

### Ranged fields

| Field | Default | Meaning |
|---|---:|---|
| `explosion_damage` | empty | Radial damage distribution. |
| `explosion_forced_procs` | empty | Guaranteed radial proc counts. |
| `multishot` | `1.0` | Native projectiles per attack. |
| `fire_rate` | `0.05` | Base attacks per second. |
| `reload_speed` | `0.0` | Reload duration in seconds. |
| `magazine_capacity` | `1` | Base magazine size. |
| `burst_count` | `1` | Attacks in each burst. |
| `burst_delay` | `0.0` | Delay between burst attacks. |
| `charge_time` | `0.0` | Charge duration per attack or burst. |
| `recharge_rate` | `0.0` | Battery recharge units per second. |
| `weakpoint_damage` | `3.0` | Base weakpoint multiplier. |

Ranged context fields include `name`, `type`, `trigger`, `is_beam`, and
`is_battery`.

### Melee fields

| Field | Default | Meaning |
|---|---:|---|
| `attack_speed` | `1.0` | Relative light-attack rate. |

Melee input currently models one abstract light attack rather than a stance
sequence.

---

## Upgrades, Ranks, Conditions, and Stacks

### Effect forms

An upgrade stat accepts these forms:

| Form | Example | Behavior |
|---|---|---|
| Static | `"base_damage": 1.65` | Always active. |
| Conditional | `{"value": 0.3, "when": "headshot"}` | Active when the named condition is truthy. |
| Stacking | `{"value": 0.1, "stacks_on": "kill"}` | Multiplied by the named stack count. |
| Rank-locked | `{"value": 0.3, "at_rank": 5}` | Added at full value once the required rank is reached. |
| Equipped requirement | `{"value": 0.55, "when_equipped": "Partner"}` | Active when the named upgrade is in the same build. |
| Multiple effects | `[1.0, {...}, {...}]` | Resolves every listed effect independently. |

Boolean effects aggregate with logical OR. Numeric values add together.
Damage-type fields aggregate into one ordered damage distribution.

### Rank scaling

Ranks are zero-based. An upgrade with `max_rank = 10` has ranks `0` through
`10`. If `rank` is omitted, the resolver uses `max_rank`; an upgrade without a
maximum rank defaults to rank `0`.

```python
serration = arsenal.get("Serration", context={"rank": 4})
assert isinstance(serration, Upgrade)
print(serration.stats.total.base_damage)  # 0.75
```

Ordinary effects use proportional scaling:

```text
(rank + 1) / (max_rank + 1)
```

Rank-locked effects are included at full value once `rank >= at_rank`.

The current resolver treats an upgrade containing any rank-locked effect as a
special case and does not proportionally scale its other effects. This matches
the current database representation but matters when creating custom upgrades.

### Stack resolution

Stack counts must be non-negative integers and are capped by `max_stacks`.
The named condition is used first; the generic `stacks` field is the fallback:

```python
upgrade = Upgrade(
    {
        "stats": {
            "crit_chance": {
                "value": 0.1,
                "stacks_on": "kill",
            }
        },
        "context": {
            "max_stacks": 5,
            "kill": 3,
        },
    }
)

print(upgrade.stats.stacking.crit_chance)  # 0.3
```

For predictable results, explicitly provide every runtime condition and stack
count that matters. A manual non-stacking condition defaults to active when it
is omitted. A stacking condition may default to `max_stacks` only while the
upgrade context contains database metadata alone; otherwise its fallback is
zero.

### Automatic weapon conditions

During weapon calculation, upgrade conditions can match the configured weapon
automatically:

- `primary`, `secondary`, and `melee`
- `rifle`, `bow`, `shotgun`, `sniper`, and `pistol`
- the normalized weapon type
- `when_equipped` requirements from the active build

A bow also satisfies the `rifle` condition.

### Build validation

Compatibility, incompatibility, requirements, slot count, duplicate upgrades,
and Exilus restrictions are database metadata only. `Build` does **not**
currently validate legal loadouts. Applications and user interfaces must
enforce those rules themselves.

---

## Reading Results

Each configured weapon exposes:

| Attribute | Description |
|---|---|
| `weapon.data` | Original weapon input and context. |
| `weapon.build` | Active build. |
| `weapon.stats` | Weapon calculator and all calculated states. |
| `weapon.format` | Text formatter. |

### Weapon state buckets

| Bucket | Description |
|---|---|
| `weapon.stats.base` | Dense, normalized weapon input. |
| `weapon.stats.modded` | Intermediate additive and locked values. |
| `weapon.stats.effective` | Final values used by expected-damage calculations. |
| `weapon.stats.average` | Expected-value outputs. |

```python
print(weapon.stats.base.damage)
print(weapon.stats.modded.crit_chance)
print(weapon.stats.effective.fire_rate)
print(weapon.stats.average.total_dps)
```

### Common average outputs

```python
average = weapon.stats.average

average.crit_chance
average.crit_multiplier
average.flat_dph
average.flat_dotph
average.total_dph
average.flat_dps
average.flat_dotps
average.total_dps
```

### Ranged outputs

```python
average.fire_rate
average.procs_per_shot
average.beam_dot_multiplier
average.weakpoint_crit_chance
average.weakpoint_crit_multiplier
average.flat_weakpoint_dph
average.flat_weakpoint_dotph
average.total_weakpoint_dph
average.flat_weakpoint_dps
average.flat_weakpoint_dotps
average.total_weakpoint_dps
```

### Mechanic-specific outputs

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

### Formatters

```python
print(weapon.format.summary())
print(weapon.format.upgrades())
```

Ranged summaries include base and effective fire-cycle stats, direct and radial
damage, weakpoint values, expected procs, DPH, DoT, and DPS. Melee summaries
include attack speed and expected damage per abstract light attack.

---

## Supported Upgrade Stats

Unknown fields can still be stored and resolved, but only fields consumed by a
weapon calculator change weapon results.

### Damage

- Damage types: `impact`, `puncture`, `slash`, `cold`, `electricity`, `heat`,
  `toxin`, `blast`, `corrosive`, `gas`, `magnetic`, `radiation`, `viral`,
  `void`, and `tau`
- `damage`
- `base_damage`
- `multiplicative_base_damage`
- `faction_damage`
- `weakpoint_damage`
- `multishot`
- `multishot_lock`

`elements` is available as a resolver bucket for preserving elemental metadata,
but it is not currently read by the weapon damage calculator. Use damage-type
fields or `damage` to modify weapon damage.

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

`melee_doughty` calculates and exposes
`weapon.stats.average.melee_doughty_bonus`, but that bonus is not yet applied to
DPH or DPS.

Upgrades do not currently add forced procs directly; forced procs come from the
weapon's `forced_procs` and `explosion_forced_procs` input fields.

---

## Calculation Scope and Assumptions

The library computes expected values rather than simulating individual attacks.
Results represent a long-run statistical average and may not match any one shot
in game.

### Damage, critical hits, and DoT

- Elemental combination order follows the order in which elemental upgrade
  entries are aggregated.
- DoT values represent the expected total damage of the modeled proc duration,
  using multipliers of `2.1` for Slash and `3.0` for Heat, Toxin, Electricity,
  and Gas.
- Faction damage is applied twice to DoT calculations.
- Radial explosion damage is added once per attack. It does not receive
  multishot, weakpoint damage, or multiplicative base damage in the current
  model.
- Native status chance is treated per projectile; expected procs per attack are
  `status_chance * multishot`.
- Forced proc counts are added independently of ordinary status weighting.
- If Hunter Munitions and Internal Bleeding produce Slash on the same attack,
  the overlap is removed once, leaving the higher of the two proc damages.

### Primary mechanics

- Hunter Munitions is modeled as an expected Slash proc chance on critical hits.
- Internal Bleeding doubles its modeled chance below `2.5` effective fire rate.
- Primed Chamber is averaged as one boosted attack per magazine and also affects
  the modeled DoT produced by that attack.
- `vigilante_bonus` is applied as an expected critical-chance tier bonus, capped
  at `0.30`.

### Secondary mechanics

- Secondary Encumber is modeled as triggering at most once per attack.
- Its chance accounts for status chance and multishot.
- Its expected DoT scales with total damage, critical damage, status damage, and
  faction damage.
- It can contribute an Impact proc to Internal Bleeding/Hemorrhage.
- Secondary Enervate uses an expected-value state calculation and exposes its
  average normal-hit and weakpoint bonuses separately.

### Fire cycle

- Positive additive fire rate reduces burst delay; negative additive fire rate
  does not increase it.
- Charge time scales with fire rate.
- `fire_rate_lock` ignores additive and multiplicative fire-rate upgrades.
- `multishot_lock` ignores modded multishot while preserving native multishot.
- Beam weapons use a baseline ammo cost of `0.5` per modeled shot/tick and apply
  their beam multishot behavior to DoT.
- Battery recharge time is `magazine_capacity / recharge_rate` and is added to
  the regular reload-time component. Reload-speed modifiers do not change the
  recharge rate itself.
- Magazine capacity uses Warframe-style true rounding and never falls below one.
- Effective fire rate is a closed-form average over charge time, burst delay,
  firing time, ammo efficiency, magazine capacity, and reload/recharge time.
  It is not a frame-by-frame simulation.

### Melee

Melee DPS is calculated as expected damage per light attack multiplied by
`attack_speed`. Stance animations, combo timing, follow-through, range, and
multi-hit attack sequences are not modeled, so melee DPS should be treated as a
relative comparison rather than literal in-game DPS.

Melee Duplicate is represented by an expected extra-hit multiplier around the
100% critical-chance region. Melee Doughty currently exposes only its calculated
bonus and does not modify damage outputs.

---

## Contributing

Bug reports, feature requests, database corrections, and pull requests are
welcome.

## License

Released under the MIT License.
