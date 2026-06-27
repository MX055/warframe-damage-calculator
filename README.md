# Warframe Average Damage Calculator

A Python library for calculating Warframe weapon damage using average damage formulas rather than simulation.

The calculator is designed to provide fast, deterministic damage calculations while remaining easy to inspect and extend.

## Supported weapons

- Melee light attacks
- Hitscan weapons
- Explosive weapons
- Projectile weapons
- Beam weapons
- Weapons with charge time

## Supported mechanics

### Damage
- Physical damage
- Elemental damage and elemental combinations
- Base damage
- Multiplicative base damage
- Faction damage

### Critical hits
- Critical chance
- Flat critical chance bonuses
- Weakpoint critical chance
- Multiplicative critical chance
- Multiplicative weakpoint critical chance
- Critical damage
- Flat critical damage bonuses
- Vigilante Set bonus

### Status
- Status chance
- Status damage
- Hunter Munitions
- Internal bleeding
- Slash, Heat, Toxin, Electricity and Gas DoTs
- Forced procs

### Weapon stats
- Attack speed
- Fire rate
- Multiplicative fire rate
- Reload speed
- Magazine capacity
- Multishot

### Special mechanics
- Primed Chamber / Charged Chamber
- Melee Duplicate

## Calculates

- Effective fire rate
- Expected status procs per shot
- Direct damage per hit (DPH)
- Direct damage per second (DPS)
- Damage over time per hit (DOTPH)
- Damage over time per second (DOTPS)
- Total damage per hit
- Total damage per second

Body-shot and weakpoint calculations are reported separately where applicable.

# Not currently supported

- Stance mods
- Combo multiplier
- Heavy attacks
- Slam attacks
- Some weapon-specific mechanics (e.g. Gotva Prime)
- Elemental imbuements
- Ammo efficiency
- Secondary encumber

# Installation

### Install directly from GitHub

```bash
pip install git+https://github.com/AAAA0001/warframe-damage-calculator.git
```

### Verify the installation

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
    galvanized_hell_stacks = 4
    primary_merciless_satcks = 12
    
    weapon = Ranged(base_damage_dist=Dist(impact=25.2, puncture=37.8, slash=27), base_fire_rate=1.42, base_reload_speed=3.00, base_magazine_capacity=20, base_multishot=6, base_crit_chance=0.30, base_crit_damage=2.80, base_status_chance=0.09)
    mod1 = Upgrade(damage_dist=Dist(impact=-0.886), crit_damage=0.855, multishot=1.126, crit_chance=0.887)
    mod2 = Upgrade(multishot=1.10 + 0.30*galvanized_hell_stacks)
    mod3 = Upgrade(base_damage=2.40)
    mod4 = Upgrade(hunter_munitions=0.30)
    mod5 = Upgrade(damage_dist=Dist(cold=1.65))
    mod6 = Upgrade(crit_damage=1.10)
    mod7 = Upgrade(crit_chance=2.00)
    mod8 = Upgrade(damage_dist=Dist(toxin=0.60), status_chance=0.60)
    mod9 = Upgrade(vigilante_bonus=0.05)
    arcane = Upgrade(base_damage=0.30*primary_merciless_satcks, reload_speed=0.30)
    buffs = Upgrade(flat_crit_damage=1.2)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, mod9, arcane, buffs)

    print(weapon.summary())

if __name__ == "__main__":
    main()
```
