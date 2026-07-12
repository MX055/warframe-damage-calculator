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
from warframe_damage_calculator import Build, Primary, Upgrade, arsenal

weapon = arsenal.get("Corinth Prime", type="primary")
multishot = arsenal.get("Galvanized Hell", type="mod")
cold = arsenal.get("Primed Chilling Grasp", type="mod")

assert isinstance(weapon, Primary)
assert isinstance(multishot, Upgrade)
assert isinstance(cold, Upgrade)

multishot.context["kill"] = 4
cold.context["rank"] = 3
weapon.configure(Build(multishot, cold))
print(weapon.format.summary())
```

For more complete examples, see the `examples/` directory.

------------------------------------------------------------------------

## Database Loader

The bundled database uses the same names as the public model constructors. The
main entry point is `arsenal.get()`:

```python
weapon = arsenal.get("Acceltra Prime", type="primary")
mod = arsenal.get("Critical Delay", type="mod")
mod.context["rank"] = 5
shotgun_names = arsenal.get(type="shotgun", attribute="name")
crit_values = arsenal.get(type="mod", attribute="crit_chance")
```

When `name` is omitted, `get()` returns all matching items. Passing
`attribute="name"` returns only their names without constructing every model.
Filters accept broad categories such as `weapon`, `upgrade`, `primary`, `mod`,
and `arcane`, as well as weapon types and triggers such as `shotgun`, `bow`, or
`semi`.

The JSON schema mirrors the model API:

- Weapon sections: `primary`, `secondary`, and `melee`.
- Upgrade sections: `mod` and `arcane`.
- Weapon damage fields: `damage` and `explosion_damage`.
- Upgrade buckets: `stats`, `conditional_stats`, and `stacking_stats`.
- Conditional entries are stored as `[value, condition]`.
- Rank-gated passive effects use `rank_locked_stats` with `[value, required_rank]`; the resolver activates them from `upgrade.context["rank"]`.

------------------------------------------------------------------------

## Web App (Streamlit)

This project also includes an interactive Streamlit UI for experimenting
with weapon base stats, mods, arcanes, and buffs without writing Python
code.

The app entry point is:

`web/app.py`

Run it from the repository root:

``` bash
py -m streamlit run web/app.py
```

If Streamlit is not installed in your environment:

``` bash
py -m pip install streamlit
```

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
    Upgrade,
    Build,
    Primary,
    Secondary,
    Melee,
)
```

 | Object      | Description                               |
 |-------------|-------------------------------------------|
 |`Upgrade`    | A single modifier (mod, arcane, or buff). |
 |`Build`      | A collection of upgrades.                 |
 |`Primary`    | Primary weapon model.                     |
 |`Secondary`  | Secondary weapon model.                   |
 |`Melee`      | Melee weapon model.                       |

Typical workflow:

1.  Create a weapon.
2.  Create one or more `Upgrade` objects.
3.  Combine them into a `Build` (optional).
4.  Apply the build with `weapon.configure(build)` or `weapon.configure(upgrade_1, upgrade_2, ...)`.
5.  Read values from `weapon.calculate`.
6.  Print results with `weapon.format.summary()`.

Since `configure()` returns the weapon, the following is also valid:

``` python
weapon = Primary(...).configure(build)
```

Weapon damage uses ordinary mappings; the optimized distribution object is
an internal calculator detail:

```python
weapon = Primary(
    damage={"impact": 20, "puncture": 30, "slash": 50},
    forced_procs={"slash": 1},
    explosion_damage={"heat": 100},
    explosion_forced_procs={"heat": 1},
)
```

------------------------------------------------------------------------

## Upgrade Fields

Upgrades store modifiers in three dictionaries. Conditional and stacking
entries use a `(value, condition)` tuple:

```python
upgrade = Upgrade(
    name="Example Arcane",
    max_stacks=3,
    stats={"reload_speed": 0.3},
    conditional_stats={"crit_chance": (0.5, "headshot")},
    stacking_stats={"base_damage": (0.3, "kill")},
)
```

Weapon and build conditions such as `bow` and `sacrificial set` resolve
automatically. Combat conditions and stack counts are stored on each upgrade:

```python
upgrade.context.update({"headshot": True, "kill": 3})
weapon.configure(build)
```

The resolver automatically adds weapon and build context to resolved upgrade
copies. When an upgrade has no context, its conditional stats default to active
and its stacking stats use `max_stacks`. Once context is supplied, omitted
manual conditions are inactive and omitted stack counts are zero. Rank-locked
stats use `upgrade.context["rank"]`. During resolution it defaults to
`max_rank`, or zero when the upgrade has no maximum rank.

The `Upgrade` and `Build` models only store data. Condition matching, stack
limits, and bucket merging are handled by `UpgradeResolver`.

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
-   `bust_delay`
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
-   The weapon firing cycle is modeled as follows. *(Testing)*

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
