# Warframe Average Damage Calculator

A Python library for deterministic Warframe weapon math using expected-value formulas (not Monte Carlo simulation).

It is built around a base -> moded -> effective stat pipeline so you can inspect every stage of the calculation.

## Current Scope

- Primary weapons
- Secondary weapons
- Melee light attacks
- Hitscan-style ranged modeling
- Beam weapons
- Charge-time weapons
- Battery reload behavior
- Direct and explosive damage components on ranged weapons

## Implemented Features

### Damage and Element Handling

- Physical and elemental damage distributions
- Elemental combinations (Blast, Corrosive, Gas, Magnetic, Radiation, Viral)
- Positive-only distribution cleanup
- IPS and elemental weighting support
- Base damage and multiplicative base damage
- Faction damage
- Weakpoint damage multiplier support

### Critical System

- Critical chance and critical damage
- Flat critical chance and flat critical damage bonuses
- Multiplicative critical chance
- Weakpoint critical chance
- Multiplicative weakpoint critical chance
- Tier-aware crit helper methods (probability and multiplier)

### Status and DoT System

- Status chance and status damage
- Expected procs-per-shot for ranged weapons
- DoT support for Slash, Heat, Toxin, Electricity, and Gas
- Forced proc distributions (main hit and explosion hit)
- Hunter Munitions (Primary)
- Internal Bleeding / Hemorrhage
- Overlap handling between Hunter Munitions and Internal Bleeding expectations
- Secondary Encumber expected-value contribution

### Weapon Stat and Fire-Cycle Modeling

- Attack speed (melee)
- Fire rate and multiplicative fire rate
- Reload speed and battery recharge contribution
- Magazine capacity
- Ammo efficiency
- Multishot
- Burst count and burst delay fields in effective fire-cycle math
- Charge time in effective fire-cycle math

### Weapon-Specific Mechanics

- Primed Chamber / Charged Chamber average multiplier (Primary)
- Vigilante set bonus applied to crit chance (Primary)
- Secondary Enervate expected stack bonus (Secondary)
- Secondary Encumber expected status package (Secondary)
- Melee Duplicate expected multiplier (Melee)
- Melee Doughty expected bonus helper (Melee)

## What You Can Calculate

### Shared Outputs

- Average critical multiplier
- Flat damage per hit (DPH)
- Flat damage per second (DPS)
- Damage-over-time per hit (DOTPH)
- Damage-over-time per second (DOTPS)
- Total damage per hit (DPH + DOTPH)
- Total damage per second (DPS + DOTPS)

### Ranged Outputs

- Average fire rate
- Expected procs per shot
- Weakpoint variants for DPH/DPS/DOTPH/DOTPS and totals

## Public API

Top-level imports:

```python
from warframe_damage_calculator import dist, Upgrade, Build, Melee, Primary, Secondary
```

Weapon workflow:

1. Create a weapon with base stats.
2. Create one or more Upgrade instances.
3. Apply them with weapon.configure(...).
4. Read numeric outputs from weapon.calculate.
5. Read formatted text from weapon.format.summary().

## Upgrade Fields

The Upgrade model currently supports:

- damage_dist
- multiplicative_base_damage, base_damage, faction_damage, weakpoint_damage
- attack_speed, multiplicative_fire_rate, fire_rate, reload_speed, magazine_capacity, ammo_efficiency, multishot
- flat_crit_chance, multiplicative_crit_chance, crit_chance
- multiplicative_weakpoint_crit_chance, weakpoint_crit_chance
- flat_crit_damage, crit_damage
- status_chance, status_damage
- hunter_munitions, internal_bleeding, primed_chamber, vigilante_bonus
- secondary_enervate, secondary_encumber
- melee_duplicate, melee_doughty
- fire_rate_lock, multishot_lock

## Assumptions

- Explosions from weapons dont benefit from *multiplicative base damage*
- If **Hunter Munitions** and **Internal Bleeding** trigger simultaneously, only the higher-damage proc is applied. *(Source: Wiki)*
- **Secondary Encumber** scales with total damage, status damage, faction damage, and critical damage. *(Source: None)*
- **Secondary Encumber** can trigger **Hemorrhage** (*Internal Bleeding*). *(Source: None)*
- **Secondary Encumber** can trigger at most once per shot. *(Source: Wiki)*
- *burst daleay* is affected by *fire rate* *(Source: None)*
- *burst delay* is not affected by negative *fire rate* *(Source: Wiki)*
- *charge time* is affected by *fire rate* *(Source: Wiki)*
- *recharge rate* is not affected by *reload speed* *(Source: Wiki)*
- *beam weapons* only consume 0.5 ammo per tick *(Source: Wiki)*
- Weapon firing cycles are assumed to work as follows. *(Source: Testing)*

```text
[ammo cost] ← (1 - [ammo efficiency]) ÷ (IF [is beam] THEN 2 ELSE 1)
[effective reload time] ← [reload time] + (IF [is battery] THEN [magazine capacity] / [recharge rate] ELSE 0)
[magazine] ← [magazine capacity]

REPEAT
    WAIT [charge time] seconds
    [primed chamber is active] ← (⌈[magazine]⌉ = [magazine capacity])

    SHOOT 1 round
    [magazine] ← [magazine] - [ammo cost]

    REPEAT [burst count] - 1 TIMES
        WAIT [burst delay] seconds
        [primed chamber is active] ← (⌈[magazine]⌉ = [magazine capacity])

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

## Quick Example

```python
from warframe_damage_calculator import *


def main():
    weapon = Primary(damage_dist=dist(impact=25.2, puncture=37.8, slash=27), fire_rate=1.42, reload_speed=3.00, magazine_capacity=20, multishot=6.00, crit_chance=0.30, crit_damage=2.80, status_chance=0.09)
    mod1 = Upgrade(damage_dist=dist(impact=-0.886), crit_damage=0.855, multishot=1.126, crit_chance=0.887)
    mod2 = Upgrade(multishot=1.10 + 0.30*4)
    mod3 = Upgrade(base_damage=2.40)
    mod4 = Upgrade(hunter_munitions=0.30)
    mod5 = Upgrade(damage_dist=dist(cold=1.65))
    mod6 = Upgrade(crit_damage=1.10)
    mod7 = Upgrade(crit_chance=2.00)
    mod8 = Upgrade(damage_dist=dist(toxin=0.60), status_chance=0.60)
    mod9 = Upgrade(vigilante_bonus=0.05)
    arcane = Upgrade(base_damage=0.30*12, reload_speed=0.30)
    buffs = Upgrade(flat_crit_damage=1.20)
    build = Build(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, mod9, arcane, buffs)
    weapon.configure(build)

    print(weapon.format.summary())

if __name__ == "__main__":
    main()
```

## Installation

Install from GitHub:

```bash
pip install git+https://github.com/AAAA0001/warframe-damage-calculator.git
```

Verify:

```python
import warframe_damage_calculator
print(warframe_damage_calculator.__version__)
```

Development install:

```bash
git clone https://github.com/AAAA0001/warframe-damage-calculator.git
cd warframe-damage-calculator
pip install -e .
```

## Running Tests

```bash
python -m unittest discover -s tests -q
```

## Not Implemented Yet

- Heavy attacks, slam attacks, stances, and combo-counter driven melee behavior
- Enemy defenses and health model (armor, shields, vulnerability, attenuation)
- Proc-side effects such as Heat/Corrosive armor strip and Viral/Magnetic health-shield multipliers
- TTK and contribution breakdown reporting
- Build import/export utilities

## Development Notes

See CHECKLIST.md for the detailed roadmap.
