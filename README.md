# Warframe Damage Calculator

An analytic Python damage calculator for Warframe weapons.

## Basic use

```python
from warframe_damage_calculator import Calculator, Loadout, arsenal

weapon = arsenal.primary.get("Phenmor")
target = arsenal.enemy.get("Heavy Gunner").set(level=200, steel_path=True)

loadout = Loadout(
    mods=[
        arsenal.mod.get("Galvanized Chamber"),
        arsenal.mod.get("Critical Delay"),
    ],
    evolutions=[
        arsenal.perk.get("Elemental Excess"),
        arsenal.perk.get("Devouring Attrition"),
    ],
)

calculator = Calculator(weapon, target, loadout)
result = calculator.resolve(attack="incarnon_form", body_part="head")
print(result.aggregate.average.total_dps)
```

`Weapon` and `Enemy` are definitions. `Loadout` owns selected mods, arcanes, and global evolution perks. `Calculator` owns one weapon-target-loadout combination, while attack selection, body-part selection, and temporary state belong to each calculation:

```python
result = calculator.resolve(attack="heavy_attack", body_part="head", state={"combo": 12})
```

## Custom definitions

Definition types are available directly from the package root, so custom content does not depend on internal module paths:

```python
from warframe_damage_calculator import Attack, AttackStats, Calculator, Compatibility, Dist, Effect, Loadout, Mod, Primary, UpgradeStats

weapon = Primary(
    name="Custom Primary",
    attacks=[Attack("shot", stats=AttackStats(damage=Dist(impact=100), fire_rate=1))],
    reload_time=1,
)
mod = Mod(
    name="Custom Mod",
    max_rank=5,
    compatibility=Compatibility(types=["primary"]),
    stats=UpgradeStats(
        damage_bonus=0.2,
        extra_attack=Effect({
            "attack": {
                "name": "aftershock",
                "trigger": "$attack",
                "delivery": "$attack",
                "form": "$attack",
                "category": "$attack",
                "aoe": True,
                "stats": {
                    "damage": {"heat": {"source": "$attack.damage.total", "multiplier": 0.1}},
                    "falloff": {"end_range": 2},
                },
            }
        }, rank_scale=False),
    ),
)
result = Calculator(weapon, loadout=Loadout(mods=[mod])).resolve()
```

`extra_attack` is a regular upgrade effect containing an attack template. A `$attack` value copies the corresponding parent-attack field; a source expression can read another parent value such as total base damage. Generated attacks therefore remain part of the upgrade definition without requiring a specialized public class or duplicating them across compatible weapons. The same root API exposes `Arcane`, `Perk`, `PerkValues`, `Effect`, `PLACEHOLDER`, all concrete weapon categories, and the enemy definition types. Calculation-result models and optimizer implementation details remain in their dedicated modules.

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
telos = arsenal.primary.get("Telos Boltor").resolve_perk(perk)
prime = arsenal.primary.get("Boltor Prime").resolve_perk(perk)
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
body = calculator.resolve(attack="incarnon_form", body_part="body")
head = calculator.resolve(attack="incarnon_form", body_part="head")
```

Each result records its selected attack and body part. Loadout optimizers can reuse the lower-level calculation engine without changing this public API.

## Optimization

On Python 3.14, the default metric is evaluated across up to four isolated interpreter workers. Candidate order, evaluation count, scores, and tie-breaking remain deterministic; parallelism changes only how independent scores in each search batch are calculated.

```python
optimized = Optimizer(calculator).resolve(attack="rocket_impact", body_part="body")
```

Use `workers=1` for sequential execution or set an explicit positive worker count to match the available CPU and memory. Custom callable metrics remain sequential because arbitrary callables and full result objects cannot safely be transferred between isolated interpreters.

## Contributions

Contribution analysis is part of the calculator workflow and includes selected upgrades, evolution perks, and progenitor bonuses:

```python
calculator = Calculator(weapon, target, loadout)
contributions = calculator.contributions(attack="incarnon_form", body_part="weakpoint")

removal = contributions.removal
contribution = contributions.contribution
```

Build contribution uses completed-build-aware permutation attribution: effects suppressed by another equipped component are evaluated with that suppressor retained. A metric name selects the chosen aggregate-average body part. `bodypart` accepts `"normal"`, `"weakpoint"`, or `"resistant"` and defaults to `"normal"`. A dotted path or callable may select another result value.

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
from warframe_damage_calculator import Formatter
from warframe_damage_calculator.formatting.objects import format_loadout, format_perk, format_upgrade, format_weapon
from warframe_damage_calculator.formatting.results import format_result

print(format_weapon(weapon))
print(format_upgrade(loadout.upgrades[0]))
print(format_perk(loadout.evolutions[0]))
print(format_loadout(loadout))
print(format_result(result))
print(Formatter(result).contributions())
```
