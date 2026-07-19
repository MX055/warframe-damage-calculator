# Warframe Damage Calculator

> Deterministic, expected-value damage calculations for Warframe weapons.

**Warframe Damage Calculator** is a Python library for comparing weapon builds
without Monte Carlo simulation. It calculates the long-run average result of an
attack from a weapon definition and a collection of upgrades.

The project is currently **alpha software**. It is useful for theorycrafting,
build comparison, and external tools, but it is not a complete simulation of
Warframe combat.

---

## Features

- Primary, Secondary, and Melee weapon models
- Direct-hit and radial explosion damage
- Physical, elemental, and combined elemental damage
- Critical chance, critical damage, status chance, and forced procs
- Expected flat damage, DoT damage, DPH, and DPS
- Beam, battery, burst-fire, and charge-weapon calculations
- Hunter Munitions, Internal Bleeding/Hemorrhage, Primed Chamber, Vigilante,
  Secondary Enervate, Secondary Encumber, and Melee Duplicate
- Bundled weapon, mod, and arcane database
- Upgrade contribution estimates

Not currently modeled: enemy defenses, damage attenuation, time-to-kill,
non-DoT status effects, projectile falloff, melee stance timing, heavy attacks,
and slam attacks.

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
from warframe_damage_calculator import Build, arsenal

weapon = arsenal.get("Corinth Prime")
build = Build(
    arsenal.get("Galvanized Hell", context={"kill": 4}),
    arsenal.get("Primed Chilling Grasp"),
    arsenal.get("Critical Delay"),
)

weapon.configure(build)

print(weapon.format.summary())
print(f"Average DPS: {weapon.stats.average.total_dps:.2f}")
```

Database upgrades resolve at maximum rank by default. Runtime conditions and
stack counts are best passed through `context`, as shown for Galvanized Hell.

For a larger build, see `examples/corinth_prime.py`.

---

## Public API

```python
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

| Object | Purpose |
|---|---|
| `Data` | Mutable mapping with nested attribute access and typed defaults. |
| `Upgrade` | One mod, arcane, buff, or other stat modifier. |
| `Build` | A collection of upgrades. |
| `Primary` | Primary ranged-weapon model. |
| `Secondary` | Secondary ranged-weapon model. |
| `Melee` | Melee light-attack model. |
| `arsenal` | Bundled weapon and upgrade database. |

A typical workflow is:

1. Load or create a weapon.
2. Load or create upgrades.
3. Set their rank, conditions, and stacks.
4. Configure the weapon with a `Build` or with individual upgrades.
5. Read calculated values from `weapon.stats`.

`configure()` returns the weapon, so chaining is supported:

```python
weapon = Primary({...}).configure(upgrade_1, upgrade_2)
```

It accepts either one `Build` or any number of `Upgrade` objects. Mixing a
`Build` and individual upgrades in the same call raises `TypeError`.

---

## Database Loader

The main database entry point is `arsenal.get()`.

### Named lookups

```python
weapon = arsenal.get("Acceltra Prime")
mod = arsenal.get("Critical Delay")
ranked_mod = arsenal.get("Critical Delay", context={"rank": 3})
base_crit = arsenal.get("Acceltra Prime", attribute="crit_chance")
```

Names are normalized for lookup. A missing name, or a name rejected by the
optional `type` filter, returns `None`.

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
model. Other attributes return a dictionary of extracted values.

The `type` argument is a broad, single matcher rather than a composable query:

- `weapon`, `upgrade`, `mod`, and `arcane` select database categories.
- `primary`, `secondary`, and `melee` match weapons in that category **and**
  upgrades compatible with it.
- `rifle`, `shotgun`, `bow`, `sniper`, `pistol`, and trigger names such as
  `semi` match relevant weapons and compatible upgrades.

For example, `arsenal.get(type="shotgun")` contains shotgun weapons as well as
shotgun-compatible mods and arcanes. Use `type="weapon"`, `type="mod"`, or
`type="arcane"` when only one database category is wanted.

The loader does not currently support combining filters such as “shotgun
weapons only” in one call.

---

## Creating Models Manually

Weapon and upgrade constructors accept a mapping with `stats` and `context`.
Nested mappings are converted to `Data` objects, so their fields can be read or
changed through attributes.

```python
from warframe_damage_calculator import Primary, Upgrade

weapon = Primary(
    {
        "stats": {
            "damage": {"impact": 20, "puncture": 30, "slash": 50},
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
        },
        "context": {
            "name": "Example Weapon",
            "type": "rifle",
            "trigger": "semi",
        },
    }
)

upgrade = Upgrade(
    {
        "stats": {
            "base_damage": 1.65,
            "crit_chance": 2.0,
            "fire_rate": -0.2,
        },
        "context": {"name": "Example Mod"},
    }
)

weapon.configure(upgrade)
```

Ranged `reload_speed` values represent reload time in seconds despite the field
name.

### Weapon input fields

Common weapon fields:

- `damage`, `forced_procs`
- `crit_chance`, `crit_damage`, `status_chance`

Ranged fields:

- `explosion_damage`, `explosion_forced_procs`
- `multishot`, `fire_rate`, `reload_speed`, `magazine_capacity`
- `burst_count`, `burst_delay`, `charge_time`, `recharge_rate`
- `weakpoint_damage`
- Context flags: `trigger`, `is_beam`, and `is_battery`

Melee fields:

- `attack_speed`

Unspecified fields use the model defaults defined by its typed `Data`
subclasses. Defaults are readable through attributes and `with_defaults()`, but
`Data` iteration and `dict(data)` include only fields explicitly supplied or
assigned. This keeps every typed `Data` object sparse without losing its normal
default-value behavior.

---

## Builds, Ranks, and Conditions

### Build copies

`Build` copies each upgrade's `data` when it is created. Set an upgrade's
runtime context before creating the build, or create a new build after changing
it:

```python
arcane = arsenal.get("Primary Merciless")
arcane.data.context.kill = 12
build = Build(arcane)
```

Changing `arcane` after `Build(arcane)` does not change the copy already stored
inside that build.

### Rank scaling

Ranks are zero-based. An upgrade with `max_rank = 10` has ranks `0` through
`10`. If `rank` is omitted, the resolver uses `max_rank`; an upgrade without a
maximum rank defaults to rank `0`.

```python
serration = arsenal.get("Serration", context={"rank": 4})
print(serration.stats.total.base_damage)  # 0.75
```

Ordinary effects use proportional rank scaling. Rank-locked effects use
`at_rank` and are included at full value only after
the required rank is reached.

```python
upgrade = Upgrade(
    {
        "stats": {
            "base_damage": 1.0,
            "reload_speed": {"value": 0.3, "at_rank": 5},
        },
        "context": {"max_rank": 10, "rank": 5},
    }
)
```

The current resolver treats an upgrade containing any rank-locked effect as a
special case and does not proportionally scale its other listed effects. This
matches the current database representation but is worth remembering when
creating custom upgrades.

### Conditional and stacking effects

A conditional effect uses `when`. A stacking effect also sets `stacking=True`
(or `stacks=True`):

```python
arcane = Upgrade(
    {
        "stats": {
            "base_damage": {"value": 0.3, "when": "headshot"},
            "crit_chance": {
                "value": 0.1,
                "when": "kill",
                "stacking": True,
            },
        },
        "context": {
            "name": "Example Arcane",
            "max_stacks": 3,
            "headshot": True,
            "kill": 2,
        },
    }
)

print(arcane.stats.conditional.base_damage)  # 0.3
print(arcane.stats.stacking.crit_chance)     # 0.2
print(arcane.stats.total.crit_chance)        # 0.2
```

Stack counts must be non-negative integers and are capped by `max_stacks`.
The generic `stacks` context field is used when the named stacking condition is
absent.

For predictable results, explicitly provide every runtime condition and stack
count that matters. The resolver currently defaults an omitted manual,
non-stacking condition to active. An omitted stacking condition may default to
`max_stacks` only when no custom runtime fields are present; otherwise it
defaults to zero. Automatic conditions such as weapon types default according
to the configured weapon.

After changing an upgrade calculator's context directly, call
`upgrade.stats.resolve()`. Weapon configuration calls the build and weapon
resolvers automatically.

### Automatic context

During weapon calculation, the resolver evaluates weapon conditions directly
from the weapon category and type without adding boolean fields to either
context. Examples include:

- `primary`, `secondary`, and `melee`
- `rifle`, `bow`, `shotgun`, `sniper`, and `pistol`
- the normalized weapon type in `weapon`
- `sacrificial set` when both Sacrificial Pressure and Sacrificial Steel are
  equipped

A bow also satisfies the `rifle` condition.

Compatibility, incompatibility, requirements, slot count, duplicate upgrades,
and Exilus restrictions are metadata only. `Build` does **not** currently
validate them; callers and user interfaces must enforce legal loadouts.

---

## Reading Results

Each configured weapon exposes these components:

| Attribute | Description |
|---|---|
| `weapon.data` | Original weapon stats and context. |
| `weapon.build` | Active build. |
| `weapon.build.stats` | Resolved and aggregated upgrade values. |
| `weapon.stats` | Weapon calculator. |
| `weapon.format` | Text formatter. |

The main weapon stat buckets are:

| Bucket | Description |
|---|---|
| `weapon.stats.base` | Normalized input weapon stats. |
| `weapon.stats.modded` | Intermediate stats after additive build effects. |
| `weapon.stats.effective` | Final stats used by damage calculations. |
| `weapon.stats.average` | Expected-value outputs. |

Common expected-value outputs include:

```python
average = weapon.stats.average

average.fire_rate
average.procs_per_shot
average.flat_dph
average.flat_dotph
average.total_dph
average.flat_dps
average.flat_dotps
average.total_dps
```

Ranged weapons also expose weakpoint variants such as
`total_weakpoint_dph` and `total_weakpoint_dps`.

Upgrade and build calculators expose the resolved buckets `static`,
`conditional`, `stacking`, `rank_locked`, and `total`.

```python
print(weapon.build.stats.total)
print(weapon.format.summary())
print(weapon.format.upgrades())
```

`weapon.format.upgrades()` reports each equipped upgrade's share of the summed
DPS contribution estimates. It is a marginal comparison, not a proof of each
upgrade's independent damage multiplier; interactions between upgrades can
make the proportions unintuitive.

---

## Supported Upgrade Stats

The current weapon calculators consume the following upgrade stats. Unknown
fields can still be stored in `Data`, but they do not affect weapon results.

### Damage

- Damage types: `impact`, `puncture`, `slash`, `cold`, `electricity`, `heat`,
  `toxin`, `blast`, `corrosive`, `gas`, `magnetic`, `radiation`, and `viral`
- `damage`, `elements`
- `base_damage`, `multiplicative_base_damage`, `faction_damage`
- `weakpoint_damage`, `multishot`, `multishot_lock`

### Fire control

- `attack_speed`
- `fire_rate`, `multiplicative_fire_rate`, `fire_rate_lock`
- `reload_speed`, `magazine_capacity`, `ammo_efficiency`

### Critical

- `crit_chance`, `flat_crit_chance`, `multiplicative_crit_chance`
- `weakpoint_crit_chance`, `multiplicative_weakpoint_crit_chance`
- `crit_damage`, `flat_crit_damage`

### Status and special effects

- `status_chance`, `status_damage`
- `hunter_munitions`, `internal_bleeding`
- `primed_chamber`, `vigilante_bonus`
- `secondary_enervate`, `secondary_encumber`
- `melee_duplicate`, `melee_doughty`

`melee_doughty` currently calculates and exposes
`weapon.stats.average.melee_doughty_bonus`, but that bonus is not yet applied to
DPH or DPS.

---

## Calculation Scope and Assumptions

The library computes expected values rather than simulating individual attacks.
Results represent a long-run statistical average and may not match any one shot
in game.

### Damage and DoT

- Elemental combination order follows the order in which elemental upgrade
  entries are aggregated.
- DoT values represent the expected total damage of the modeled proc duration,
  using multipliers of `2.1` for Slash and `3.0` for Heat, Toxin, Electricity,
  and Gas.
- Faction damage is applied twice to DoT calculations.
- Radial explosion damage is added once per attack. It does not receive
  multishot, weakpoint damage, or multiplicative base damage in the current
  model.
- If Hunter Munitions and Internal Bleeding produce Slash on the same attack,
  the overlap is counted once using the higher of the two proc damages.
- Forced procs come from the weapon's `forced_procs` and
  `explosion_forced_procs` fields; upgrades do not currently add forced procs.

### Secondary Encumber

- Encumber is modeled as triggering at most once per attack.
- Its chance accounts for status chance and multishot.
- Its expected DoT scales with total damage, critical damage, status damage,
  and faction damage.
- It can contribute an Impact proc to Internal Bleeding/Hemorrhage.

### Fire cycle

- Positive additive fire rate reduces burst delay; negative additive fire rate
  does not increase it.
- Charge time scales with fire rate.
- Beam weapons use a baseline ammo cost of `0.5` per modeled shot/tick.
- Battery recharge time is `magazine_capacity / recharge_rate` and is added to
  the regular reload-time component. Reload-speed modifiers do not change the
  recharge rate itself.
- Primed Chamber is averaged as one boosted attack per magazine.
- Effective fire rate is a closed-form average over charge time, burst delay,
  firing time, ammo efficiency, magazine capacity, and reload/recharge time.
  It is not a frame-by-frame weapon simulation.

### Melee

Melee DPS is calculated as expected damage per light attack multiplied by
`attack_speed`. Stance animations, combo timing, follow-through, range, and
multi-hit attack sequences are not modeled, so melee DPS should be treated as a
relative comparison rather than literal in-game DPS.

---

## Contributing

Bug reports, feature requests, and pull requests are welcome.

## License

Released under the MIT License.
