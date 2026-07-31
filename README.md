# Warframe Damage Calculator

An analytic Python damage calculator for Warframe weapons.

## Basic use

```python
from warframe_damage_calculator import Calculator, Loadout, arsenal

weapon = arsenal.weapon.get("Phenmor")
target = arsenal.enemy.get("Heavy Gunner").set(level=200, steel_path=True)

loadout = Loadout(
    upgrades=[
        arsenal.upgrade.get("Galvanized Chamber"),
        arsenal.upgrade.get("Critical Delay"),
    ],
    evolutions=[
        arsenal.perk.get("Elemental Excess"),
        arsenal.perk.get("Devouring Attrition"),
    ],
)

calculator = Calculator(weapon, target, loadout)
result = calculator.calculate(attack="incarnon_form", bodypart="head")
print(result.aggregate.average.normal.total_dps)
```

`Weapon` and `Enemy` are definitions. `Loadout` owns selected upgrades and global evolution perks. `Calculator` owns one weapon-target-loadout combination, while attack selection, body-part selection, and temporary state belong to each calculation:

```python
result = calculator.calculate(attack="heavy_attack", bodypart="head", state={"combo": 12})
```

## Global perks

Perks are loaded independently of weapons:

```python
perk = arsenal.perk.get("Devouring Attrition")
```

A global `Perk` owns the complete effect template: affected stats, modes, families, conditions, automatic behavior, and placeholder positions. A weapon owns a `PerkValues` entry containing only the concrete values for those positions.

```text
global Perk template + weapon PerkValues -> ResolvedPerk -> effect pipeline
```

The same template can resolve to different values:

```python
perk = arsenal.perk.get("Elemental Balance")
telos = arsenal.weapon.get("Telos Boltor").resolve_perk(perk)
prime = arsenal.weapon.get("Boltor Prime").resolve_perk(perk)
```

Every selected item in `Loadout.evolutions` is resolved through the weapon before calculation. Missing values, unknown values, duplicate tier selections, and perks unavailable to the weapon are rejected. Tier and choice data are retained in `weapon.perk_choices` for selection and optimizer search spaces; calculation does not convert selected perks back into database instructions.

## Result navigation

Results use one navigation rule:

```text
scope -> pool -> target zone -> metric
```

The aggregate scope is the selected root attack including every descendant:

```python
result.aggregate.average.normal.total_dps
result.aggregate.average.weakpoint.total_dph
result.aggregate.status
```

The attack scope is one individual component:

```python
projectile = result.attacks["air_burst_projectile"]
projectile.base
projectile.modded
projectile.effective
projectile.upgrades
projectile.evolutions
projectile.average
projectile.average.normal.total_dps
projectile.status
projectile.spatial
```

`result.selected_attack` identifies the selected root. `result.attacks.keys()` lists the components included in its final damage. Aggregate results intentionally do not expose a combined critical chance or other meaningless cross-component weapon stats.

Damage zones are `normal`, `weakpoint`, and `resistant`. Each available zone exposes:

```python
direct_dph
dot_dph
total_dph
direct_dps
dot_dps
total_dps
```

## Repeated calculations

A calculator keeps one loadout fixed while allowing repeated attack and body-part calculations:

```python
calculator = Calculator(weapon, target, loadout)
body = calculator.calculate(attack="incarnon_form", bodypart="body")
head = calculator.calculate(attack="incarnon_form", bodypart="head")
```

Each result records its selected attack and body part. Loadout optimizers can reuse the lower-level calculation engine without changing this public API.

## Contributions

Both contribution methods evaluate immutable calculator inputs and include selected upgrades and evolution perks:

```python
from warframe_damage_calculator import removal_contributions, shapley_contributions

removal = removal_contributions(calculator, loadout, attack="incarnon_form", bodypart="weakpoint")
shapley = shapley_contributions(calculator, loadout, attack="incarnon_form", bodypart="weakpoint")
```

A metric name selects the chosen aggregate-average body part. `bodypart` accepts `"normal"`, `"weakpoint"`, or `"resistant"` and defaults to `"normal"`. A dotted path or callable may select another result value.

## Spatial output

Ordinary DPH and DPS never assume enemy density, spacing, alignment, or an arbitrary target cap. Punch through remains an ordinary mechanical stat:

```python
result.attacks[result.selected_attack].effective.punch_through
```

An AoE component may expose raw analytic damage mass:

```python
spatial = result.attacks["air_burst_explosion"].spatial
spatial.dimension
spatial.damage_mass
spatial.normal.total_dph_mass
spatial.normal.total_dps_mass
```

The `_mass` suffix and dimension distinguish these values from ordinary damage.

## Formatting

Formatting is separate from definitions and calculation:

```python
from warframe_damage_calculator import ResultFormatter, format_loadout, format_perk, format_result, format_upgrade, format_weapon

print(format_weapon(weapon))
print(format_upgrade(loadout.upgrades[0]))
print(format_perk(loadout.evolutions[0]))
print(format_loadout(loadout))
print(format_result(result))
print(ResultFormatter(result).contributions())
```
