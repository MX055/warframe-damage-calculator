# Warframe Damage Calculator

> Deterministic Warframe weapon damage calculations using expected-value
> formulas.

**Warframe Damage Calculator** is a Python library for modeling Warframe
weapon performance using deterministic mathematics rather than Monte
Carlo simulation. Instead of simulating thousands of shots, the library
computes the statistical average outcome of every attack, making it
suitable for build optimization, theorycrafting, and external tooling.

The project is built around a simple object-oriented API with reusable
weapon definitions, upgrades, and builds.

------------------------------------------------------------------------

## Features

-   Deterministic expected-value calculations
-   Primary, Secondary, and Melee weapon support
-   Beam, battery, burst-fire, and charge weapon support
-   Physical, elemental, and combined elemental damage
-   Critical and status systems
-   Hunter Munitions, Hemorrhage, Secondary Enervate, Secondary
    Encumber, Melee Duplicate, Melee Doughty, Primed Chamber, and
    Vigilante support
-   Flat and damage-over-time calculations
-   Small, Pythonic public API

------------------------------------------------------------------------

## Requirements

-   Python **3.14+**

------------------------------------------------------------------------

## Installation

``` bash
pip install git+https://github.com/MX055/warframe-damage-calculator.git
```

Development install:

``` bash
git clone https://github.com/MX055/warframe-damage-calculator.git
cd warframe-damage-calculator
pip install -e .
```

------------------------------------------------------------------------

## Quick Start

``` python
from warframe_damage_calculator import Build, arsenal

weapon = arsenal.get("Corinth Prime")
multishot = arsenal.get("Galvanized Hell")
cold = arsenal.get("Primed Chilling Grasp")

multishot.data.context.kill = 4
cold.data.context.rank = 3
weapon.configure(Build(multishot, cold))
print(weapon.format.summary())
```

For more complete examples, see the `examples/` directory.

------------------------------------------------------------------------

## Database Loader

The bundled database uses the same names as the public model constructors. The
main entry point is `arsenal.get()`:

```python
weapon = arsenal.get("Acceltra Prime")
mod = arsenal.get("Critical Delay", context={"rank": 5})
shotgun_names = arsenal.get(type="shotgun", attribute="name")
crit_values = arsenal.get(type="mod", attribute="crit_chance")
```

Named lookups return the single matching weapon or upgrade without requiring `type`. When `name` is omitted, `get()` returns all matching items. Passing
`attribute="name"` returns only their names without constructing every model.
Filters accept broad categories such as `weapon`, `upgrade`, `primary`, `mod`,
and `arcane`, as well as weapon types and triggers such as `shotgun`, `bow`, or
`semi`.

The JSON schema mirrors the model API:

- Weapon sections: `primary`, `secondary`, and `melee`.
- Upgrade sections: `mod` and `arcane`.
- Weapon damage fields: `damage` and `explosion_damage`.
- Upgrade effects all live in `stats`; effect objects use `value`, `when`, and optional `stacking` fields.

------------------------------------------------------------------------

## Design

Every weapon follows the same pipeline:

``` text
Base weapon
      │
      ▼
Build (mods, arcanes, buffs)
      │
      ▼
Derived statistics
      │
      ▼
Damage calculations
      │
      ▼
Formatted output
```

The library separates responsibilities into models, calculators, and
formatters so the same weapon definition can be reused with different
builds.

------------------------------------------------------------------------

## Public API

``` python
from warframe_damage_calculator import (
    Data,
    Upgrade,
    Build,
    Melee,
    Primary,
    Secondary,
    arsenal,
)
```

| Object      | Description                               |
|-------------|-------------------------------------------|
| `Data`      | Nested dictionary with attribute access.  |
| `Upgrade`   | A single modifier (mod, arcane, or buff). |
| `Build`     | A collection of upgrades.                 |
| `Primary`   | Primary weapon model.                     |
| `Secondary` | Secondary weapon model.                   |
| `Melee`     | Melee weapon model.                       |
| `arsenal`   | Bundled weapon and upgrade database.      |

Typical workflow:

1.  Create a weapon.
2.  Create one or more `Upgrade` objects.
3.  Combine them into a `Build` (optional).
4.  Apply the build with `weapon.configure(build)` or `weapon.configure(upgrade_1, upgrade_2, ...)`.
5.  Read source values from `weapon.data` and calculated values from `weapon.stats`.
6.  Print results with `weapon.format.summary()`.

Since `configure()` returns the weapon, the following is also valid:

``` python
weapon = Primary(...).configure(build)
```

Weapon and upgrade builders accept one dictionary containing `stats` and `context`. `Data` exposes nested fields as attributes:

```python
weapon = Primary(
  {
    "stats": {
        "damage": {"impact": 20, "puncture": 30, "slash": 50},
        "forced_procs": {"slash": 1},
        "explosion_damage": {"heat": 100},
        "explosion_forced_procs": {"heat": 1},
    },
    "context": {"type": "rifle"},
  }
)
```

Each weapon exposes three main components:

| Attribute | Description |
|-----------|-------------|
| `weapon.data` | Original weapon data, containing `stats` and `context`. |
| `weapon.stats` | Calculator with `base`, `moded`, and `effective` stat buckets. |
| `weapon.format` | Formatter for summaries and upgrade contribution output. |

Use `weapon.format.upgrades()` to format the calculated contribution of each
upgrade in the active build.

------------------------------------------------------------------------

## Upgrade Fields

An upgrade stat may be a number, a damage distribution, a single conditional
effect, or a list mixing those forms. Effects may be conditional, stacking,
or rank-locked:

```python
upgrade = Upgrade(
  {
    "stats": {
        "reload_speed": 0.3,
        "damage": [
            {"impact": 1.2, "slash": 0.6},
            {"value": {"heat": 0.6}, "when": "roll"},
        ],
        "crit_chance": [0.5, {"value": 0.1, "when": "kill", "stacking": True}],
        "base_damage": {"value": 0.3, "when": "headshot"},
    },
    "context": {"name": "Example Arcane", "max_stacks": 3, "kill": 3},
  }
)
```

Descriptive metadata is stored only in `context`. Upgrade contexts include
`name`, `category`, `compatibility`, `incompatibility`, `requirements`,
`max_rank`, `max_stacks`, and `is_exilus`; weapon contexts include `name`,
`category`, `type`, and ranged trigger/beam/battery metadata when applicable.
Runtime conditions remain in the same internal context object.

Weapon calculations expose attribute-accessible `base`, `moded`, and
`effective` stat buckets. Read calculated values through attributes, for
example, `weapon.stats.effective.crit_chance`.

Weapon and build conditions such as `bow` and `sacrificial set` resolve
automatically. Combat conditions and stack counts are stored on each upgrade:

```python
upgrade.data.context.headshot = True
upgrade.data.context.kill = 3
weapon.configure(build)
```

### Context Examples

#### Rank scaling

`max_rank` describes the upgrade's maximum zero-based rank. If `rank` is
omitted, the upgrade resolves at `max_rank`. Otherwise scalar effects are
scaled by `(rank + 1) / (max_rank + 1)`:

```python
ranked = Upgrade(
  {
    "stats": {"crit_chance": 1.2},
    "context": {"name": "Ranked Mod", "max_rank": 5, "rank": 2},
  }
)

resolved = ranked.resolve()
print(resolved.data.stats.crit_chance)  # 0.6: 1.2 * (2 + 1) / (5 + 1)
```

A rank requirement uses a mapping in `when`. Unlike a normally scaled effect,
the value is either included in full or omitted:

```python
rank_locked = Upgrade(
  {
    "stats": {"multishot": {"value": 0.5, "when": {"rank": 3}}},
    "context": {"max_rank": 5, "rank": 3},
  }
)

print(rank_locked.resolve().data.stats.multishot)  # 0.5
```

#### Conditions and stacks

The `when` string names a context field. A non-stacking effect uses its truth
value; a stacking effect uses it as a non-negative stack count:

```python
arcane = Upgrade(
  {
    "stats": {
        "base_damage": {"value": 0.3, "when": "headshot"},
        "crit_chance": {"value": 0.1, "when": "kill", "stacking": True},
    },
    "context": {
        "name": "Example Arcane",
        "max_stacks": 3,
        "headshot": True,
        "kill": 2,
    },
  }
)

resolved = arcane.resolve()
print(resolved.data.stats.base_damage)  # 0.3
print(resolved.data.stats.crit_chance)  # 0.2: 0.1 * 2 stacks
```

Stack counts are capped by `max_stacks`. The generic `stacks` field is used
when the specifically named condition is absent:

```python
arcane.data.context.kill = 10
print(arcane.resolve().data.stats.crit_chance)  # 0.3: capped at 3 stacks

del arcane.data.context.kill
arcane.data.context.stacks = 1
print(arcane.resolve().data.stats.crit_chance)  # 0.1
```

If a context contains only descriptive metadata and automatic weapon fields,
manual conditions default to active and stacking effects default to
`max_stacks`. Adding any manual condition switches omitted manual conditions
and stack counts to inactive/zero, so set every runtime condition you want to
model explicitly.

#### Weapon and build context

Calculators keep the configured upgrades unchanged and apply automatic weapon
and build context when calculations run. A bow is also treated as a rifle for
compatibility conditions:

```python
bow = arsenal.get("Paris Prime")
rifle_bonus = Upgrade(
  {
    "stats": {"base_damage": {"value": 0.2, "when": "rifle"}},
    "context": {"name": "Rifle Bonus"},
  }
)

bow.configure(rifle_bonus)
resolved = rifle_bonus.resolve(build=bow.build.data, weapon=bow.data)
print(resolved.data.context.weapon)  # "bow"
print(resolved.data.context.bow)     # True
print(resolved.data.context.rifle)   # True
```

Build-wide conditions can depend on upgrade names. Equipping both Sacrificial
mods enables `sacrificial set` on every upgrade in that build:

```python
melee = arsenal.get("Ack & Brunt")
pressure = arsenal.get("Sacrificial Pressure")
steel = arsenal.get("Sacrificial Steel")

melee.configure(pressure, steel)
for upgrade in melee.build:
    resolved = upgrade.resolve(build=melee.build.data, weapon=melee.data)
    print(resolved.data.context["sacrificial set"])  # True
```

During calculation, shared weapon and build values are applied to each upgrade
without modifying its stored context. These include normalized weapon-type
flags, the weapon type, and the `sacrificial set` condition. Rank-locked stats
use `upgrade.data.context.rank`; it defaults to `max_rank`, or zero when the
upgrade has no maximum rank.

The `Upgrade` and `Build` models store data. Condition matching, rank scaling,
stack limits, and effect merging are handled by `UpgradeCalculator` when
`Upgrade.resolve()` is called.

### Damage

-   `damage`
-   `base_damage`
-   `multiplicative_base_damage`
-   `faction_damage`
-   `weakpoint_damage`
-   `multishot`

### Fire Control

-   `attack_speed`
-   `fire_rate`
-   `multiplicative_fire_rate`
-   `burst_count`
-   `burst_delay`
-   `charge_time`
-   `reload_speed`
-   `recharge_rate`
-   `ammo_efficiency`
-   `magazine_capacity`
-   `is_beam`
-   `is_battery`

### Critical

-   `crit_chance`
-   `flat_crit_chance`
-   `multiplicative_crit_chance`
-   `weakpoint_crit_chance`
-   `multiplicative_weakpoint_crit_chance`
-   `crit_damage`
-   `flat_crit_damage`

### Status

-   `forced_procs`
-   `status_chance`
-   `status_damage`

### Special Effects

-   `hunter_munitions`
-   `internal_bleeding`
-   `primed_chamber`
-   `vigilante_bonus`
-   `secondary_enervate`
-   `secondary_encumber`
-   `melee_duplicate`
-   `melee_doughty`

------------------------------------------------------------------------

## Supported Features

### Weapons

- [x] Primary weapons
- [x] Secondary weapons
- [x] Melee light attacks
- [x] Beam weapons
- [x] Hitscan weapons
- [x] Charge weapons
- [x] Battery weapons
- [x] Burst-fire weapons
- [ ] Melee heavy attacks
- [ ] Melee slam attacks
- [ ] Projectile falloff

### Damage

- [x] Physical damage
- [x] Elemental damage
- [x] Combined elements
- [x] Damage weighting
- [x] Base, multiplicative, faction, and weakpoint damage
- [x] Critical calculations
- [ ] Enemy defenses and damage attenuation

### Status

- [x] Expected status procs
- [x] DoT status effects
- [x] Forced procs
- [x] Hunter Munitions
- [x] Internal Bleeding / Hemorrhage
- [x] Secondary Encumber
- [ ] Non-DoT status effects

### Calculations

- [x] Flat DPH / DPS
- [x] DoT DPH / DPS
- [x] Total DPH / DPS
- [x] Effective fire rate
- [x] Expected status procs per shot
- [x] Damage contribution breakdowns
- [ ] Time-to-kill

------------------------------------------------------------------------

## Assumptions

The library computes **expected values** rather than simulating
individual shots. Results therefore represent the statistical long-term
average and may not exactly match any single shot fired in-game.

### Damage

-   Explosive damage does **not** benefit from **multiplicative base
    damage**.
-   If **Hunter Munitions** and **Internal Bleeding (Hemorrhage)**
    trigger simultaneously, only the higher-damage Slash proc is
    counted. *(Wiki)*

### Secondary Encumber

-   Secondary Encumber scales with total damage, status damage, faction
    damage, and critical damage.
-   Secondary Encumber can trigger Hemorrhage.
-   Secondary Encumber can trigger at most once per shot. *(Wiki)*

### Fire Cycle

-   Burst delay is affected by positive fire rate.
-   Burst delay is not reduced by negative fire rate. *(Wiki)*
-   Charge time scales with fire rate. *(Wiki)*
-   Recharge rate is independent of reload speed. *(Wiki)*
-   Beam weapons consume **0.5 ammo per tick**. *(Wiki)*
-   The weapon firing cycle is modeled as follows.

``` text
[ammo cost] ← (1 - [ammo efficiency]) ÷ (IF [is beam] THEN 2 ELSE 1)
[effective reload time] ← [reload time] + (IF [is battery] THEN [magazine capacity] / [recharge rate] ELSE 0)
[magazine] ← [magazine capacity]

REPEAT
    WAIT [charge time] seconds
    [primed chamber is active] ← ⌈[magazine]⌉ = [magazine capacity]

    SHOOT 1 round
    [magazine] ← [magazine] - [ammo cost]

    REPEAT [burst count] - 1 TIMES
        WAIT [burst delay] seconds
        [primed chamber is active] ← ⌈[magazine]⌉ = [magazine capacity]

        SHOOT 1 round
        [magazine] ← [magazine] - [ammo cost]

        IF [magazine] ≤ 0 THEN
            BREAK
    END REPEAT

    IF [magazine] ≤ 0 THEN
        WAIT [effective reload time] seconds
        [magazine] ← [magazine capacity]
    ELSE
        WAIT 1 ÷ [fire rate] seconds
    END IF
END REPEAT
```

------------------------------------------------------------------------

## Contributing

Bug reports, feature requests, and pull requests are welcome.

## License

Released under the MIT License.
