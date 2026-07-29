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

Effects contain exactly three dictionary channels:

```python
from warframe_damage_calculator import Effect

effect = Effect(
    properties={"value": 0.4, "family": "status"},
    manual={"when": "on_kill", "stacks": 2, "for": 20},
    automatic={"with": "unique_status_count", "stacks": "inf"},
)
```

`properties` owns scalar value, mode, family, rank scaling, and caps. `manual` owns conditions supplied by the caller. `automatic` owns combat state calculated by the engine. Values use their native JSON/Python types, so stack counts and durations are numbers rather than encoded strings. Multiple simultaneous conditions use a list in `when`.

Automatic behavior stays flat. `on` names an event, `when` names a condition, `chance` is its probability, and `with` names a multiplier calculated by the engine. Multiple applications are separate effects:

```python
slash_proc = [
    Effect(properties={"value": 1}, automatic={"on": "impact_status_proc", "chance": 0.35}),
    Effect(properties={"value": 1}, automatic={"on": "impact_status_proc", "when": "fire_rate_below_2.5", "chance": 0.35}),
]
fire_rate = [
    Effect(properties={"value": 0.6}),
    Effect(properties={"value": 0.6}, automatic={"when": "bow_weapon"}),
]
synth_charge = Effect(
    properties={"value": 2, "family": "magazine_last_shot"},
    automatic={"on": "magazine_last_shot", "when": ["non_continuous_fire", "normal_form", "magazine_at_least_5"]},
)
vigilante_bonus = Effect(
    properties={"value": 1, "mode": "flat"},
    automatic={"on": "critical_hit", "chance": 0.05},
)
```

Tags follow one vocabulary: manual events begin with `on_`, ongoing states begin with `while_`, status events end in `_status_proc`, comparisons use words such as `_below_`, `_above_`, or `_at_least_`, and units are written out (`10_meters`, `0.2_seconds`, `90_percent`). The `on` field omits the redundant `on_` prefix because the field already supplies it.

Proc and result identity are expressed by the stat name (`slash_proc`, `puncture_proc`, `crit_tier`, and so on); effects do not use a generic `target` field. An attack's intrinsic `forced_procs` distribution remains part of its attack data. Form applicability also uses `when`, such as `{"when": "incarnon_form"}`; there is no separate scope language.

Runtime state retains the value supplied by the caller. Each effect applies its own stack cap during resolution.

Compatibility metadata only produces warnings. Automatic `when` conditions define where an effect actually applies.

## Calculation coverage

The engine includes ranged and melee rates, charge/burst/reload/battery cycles, Incarnon charge pools and form-conditioned evolutions, elemental ordering, additive and multiplicative Condition Overload, status uptime and stack windows, forced procs, damage-over-time effects, first/last magazine mixtures, nested attack trees, stance and combo calculations, special arcane/mod behaviors, enemy scaling and defenses, hit zones, and removal/Shapley contribution analysis.

## Isolated validation

Run from this directory:

```bash
python -P -B -m unittest discover -s tests -v
```

The suite validates direct construction, effect-channel boundaries, repositories, all 656 weapons, all 779 upgrades against primary/secondary/melee engines, all 877 enemies, every selectable evolution and attack, and fixed combat-parity scenarios.
