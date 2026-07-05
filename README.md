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

-   Python **3.12+**

------------------------------------------------------------------------

## Installation

``` bash
pip install git+https://github.com/AAAA0001/warframe-damage-calculator.git
```

Development install:

``` bash
git clone https://github.com/AAAA0001/warframe-damage-calculator.git
cd warframe-damage-calculator
pip install -e .
```

------------------------------------------------------------------------

## Quick Start

``` python
from warframe_damage_calculator import *

weapon = Primary(
    damage_dist=dist(slash=120),
    fire_rate=5,
    crit_chance=0.30,
    crit_damage=2.0,
)

build = Build(
    Upgrade(base_damage=1.65),
    Upgrade(multishot=1.20),
    Upgrade(crit_chance=2.00),
)

weapon.configure(build)

print(weapon.format.summary())
```

For more complete examples, see the `examples/` directory.

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
    dist,
    Upgrade,
    Build,
    Primary,
    Secondary,
    Melee,
)
```

  Object        Description
  ------------- -------------------------------------------
  `dist`        Damage distribution.
  `Upgrade`     A single modifier (mod, arcane, or buff).
  `Build`       A collection of upgrades.
  `Primary`     Primary weapon model.
  `Secondary`   Secondary weapon model.
  `Melee`       Melee weapon model.

Typical workflow:

1.  Create a weapon.
2.  Create one or more `Upgrade` objects.
3.  Combine them into a `Build`.
4.  Apply the build with `weapon.configure(build)`.
5.  Read values from `weapon.calculate`.
6.  Print results with `weapon.format.summary()`.

Since `configure()` returns the weapon, the following is also valid:

``` python
weapon = Primary(...).configure(build)
```

------------------------------------------------------------------------

## Upgrade Fields

### Damage

-   `damage_dist`
-   `base_damage`
-   `multiplicative_base_damage`
-   `faction_damage`
-   `weakpoint_damage`

### Fire Control

-   `attack_speed`
-   `fire_rate`
-   `multiplicative_fire_rate`
-   `reload_speed`
-   `magazine_capacity`
-   `ammo_efficiency`
-   `multishot`

### Critical

-   `crit_chance`
-   `flat_crit_chance`
-   `multiplicative_crit_chance`
-   `weakpoint_crit_chance`
-   `multiplicative_weakpoint_crit_chance`
-   `crit_damage`
-   `flat_crit_damage`

### Status

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
- [ ] Projectile falloff

### Damage

- [x] Physical damage
- [x] Elemental damage
- [x] Combined elements
- [x] IPS weighting
- [x] Base, faction, and weakpoint damage
- [x] Critical calculations
- [ ] Enemy defenses and damage attenuation

### Status

- [x] Expected status procs
- [x] Damage-over-time
- [x] Forced procs
- [x] Hunter Munitions
- [x] Hemorrhage
- [x] Secondary Encumber
- [ ] Viral, Corrosive, Heat, and Magnetic secondary effects

### Calculations

- [x] Flat DPH / DPS
- [x] DoT DPH / DPS
- [x] Total DPH / DPS
- [x] Effective fire rate
- [x] Expected status procs per shot
- [ ] Time-to-kill
- [ ] Damage contribution breakdowns

------------------------------------------------------------------------

## Running Tests

``` bash
python -m unittest discover -s tests -q
```

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

The weapon firing cycle is modeled as follows:

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
