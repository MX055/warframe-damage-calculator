# Warframe Damage Calculator 1.0

This directory contains a complete, independent implementation of the calculator, catalog, public API, formatters, and tests.

## API

```python
from warframe_damage_calculator import Build, Dist, arsenal

weapon = arsenal.weapon.get("Corinth Prime")
build = Build(
    arsenal.upgrade.get("Galvanized Hell").set(on_kill=4),
    arsenal.upgrade.get("Critical Deceleration"),
    arsenal.upgrade.get("Primed Ravage"),
)
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)

weapon.set(attack="air_burst_projectile").configure(build, target)

print(weapon.name)
print(weapon.attacks[weapon.runtime.attack].stats.damage)
print(weapon.results.main.final.total_dps)
print(weapon.format.summary())
```

Repositories are category-specific. Missing records raise `KeyError`:

```python
arsenal.weapon.get("Braton")
arsenal.upgrade.get("Serration")
arsenal.enemy.get("Heavy Gunner")
```

Definitions expose direct attributes. There is no `.data` wrapper.

`weapon.set(...)`, `upgrade.set(...)`, `build.set(...)`, and `enemy.set(...)` mutate and return the same object. `weapon.configure(build, target)` stores independent copies of the build and target.

`Dist` is the ordered damage distribution used by attack definitions and results:

```python
damage = Dist(impact=100, toxin=90, cold=90)
print(damage.combine_elements())  # Dist(impact=100.0, viral=180.0)
```

## Effects

Effects contain exactly three token channels:

```python
from warframe_damage_calculator import Effect

effect = Effect(
    properties=["VALUE:0.4", "FAMILY:STATUS"],
    manual=["WHEN:ON_KILL", "STACKS:2", "FOR:20"],
    automatic=["WITH:UNIQUE_STATUS_COUNT", "STACKS:INF"],
)
```

`properties` owns scalar value, mode, family, rank scaling, and caps. `manual` owns conditions supplied by the caller. `automatic` owns combat state calculated by the engine. The compiler enforces separate opcode vocabularies for the two behavior channels. Durations and stack limits are unitless token operands (`FOR:20`, `STACKS:2`).

Runtime state retains the value supplied by the caller. Each effect applies its own stack cap during resolution.

Compatibility metadata only produces warnings. Effects still resolve; `SCOPE` and `EXCLUDE` automatic tokens define where an effect actually applies.

## Calculation coverage

The engine includes ranged and melee rates, charge/burst/reload/battery cycles, Incarnon charge pools and scoped evolutions, elemental ordering, additive and multiplicative Condition Overload, status uptime and stack windows, forced procs, damage-over-time effects, first/last magazine mixtures, nested attack trees, stance and combo calculations, special arcane/mod behaviors, enemy scaling and defenses, hit zones, and removal/Shapley contribution analysis.

## Isolated validation

Run from this directory:

```bash
python -P -B -m unittest discover -s tests -v
```

The suite validates direct construction, token boundaries, repositories, all 656 weapons, all 779 upgrades against primary/secondary/melee engines, all 877 enemies, every selectable evolution and attack, and fixed combat-parity scenarios.
