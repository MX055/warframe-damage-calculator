# Warframe Average Damage Calculator

A Python library for calculating Warframe weapon damage using average damage formulas rather than simulation.

The calculator is designed to provide fast, deterministic damage calculations while remaining easy to inspect and extend.

## Supported Weapons

- Melee Light Attacks
- Hitscan Weapons
- Explosive Weapons
- Projectile Weapons
- Beam Weapons
- Weapons With Charge Time

## Supported Mechanics

### Damage
- Physical Damage
- Elemental Damage & Elemental Combinations
- Base Damage
- Multiplicative Base Damage
- Faction Damage

### Critical Hits
- Critical Chance
- Flat Critical Chance Bonuses
- Weakpoint Critical Chance
- Multiplicative Critical Chance
- Multiplicative Weakpoint Critical Chance
- Critical Damage
- Flat Critical Damage Bonuses
- Vigilante Set Bonus
- Melee Doughty

### Status
- Status Chance
- Status Damage
- Hunter Munitions
- Internal Bleeding
- Slash, Heat, Toxin, Electricity & Gas DoTs
- Forced Procs

### Weapon Stats
- Attack Speed
- Fire Rate
- Multiplicative Fire Rate
- Reload Speed
- Magazine Capacity
- Multishot

### Special Mechanics
- Primed Chamber / Charged Chamber
- Secondary Enervate
- Melee Duplicate

## Calculates

- Effective Fire Rate
- Expected Status Procs / Shot
- Direct Damage / Hit (DPH)
- Direct Damage / Second (DPS)
- Damage Over Time / Hit (DOTPH)
- Damage over time / Second (DOTPS)
- Total Damage / Hit (DPH + DOTPH)
- Total Damage / Second (DPS + DOTPS)

Body-shot and weakpoint calculations are reported separately where applicable.

# Not Currently Supported

- Stance Mods
- Combo Multiplier
- Heavy Attacks
- Slam Attacks
- Some Weapon-Specific Mechanics (e.g. Gotva Prime)
- Elemental Imbuements
- Secondary Encumber

# Installation

### Install Directly From GitHub

```bash
pip install git+https://github.com/AAAA0001/warframe-damage-calculator.git
```

### Verify The Installation

Open Python and run:

```python
import warframe_damage_calculator

print(warframe_damage_calculator.__version__)
```

## Development Installation

Clone the repository:

```bash
git clone https://github.com/AAAA0001/warframe-damage-calculator.git
```

Enter the project directory:

```bash
cd warframe-damage-calculator
```

Install in editable mode:

```bash
pip install -e .
```

# Example
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
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, mod9, arcane, buffs)

    print(weapon.format.summary())

if __name__ == "__main__":
    main()
```
