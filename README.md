# Warframe Damage Calculator 1.0

This directory contains a complete, independent implementation of the calculator, catalog, public API, formatters, and tests.

## API

```python
from warframe_damage_calculator import Build, Dist, arsenal

weapon = arsenal.weapon.get("Corinth Prime")
build = Build(
    arsenal.upgrade.get("Galvanized Hell").set(kill=4),
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
    manual={"when": "kill", "stacks": 2, "for": 20},
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

Tags follow one vocabulary: event conditions use direct names such as `kill` and `headshot`, ongoing states begin with `while_`, status events end in `_status_proc`, comparisons use words such as `_below_`, `_above_`, or `_at_least_`, and units are written out (`10_meters`, `0.2_seconds`, `90_percent`). Both manual `when` values and automatic `on` values omit the redundant `on_` prefix because their fields already supply the relationship.

Proc and result identity are expressed by the stat name (`slash_proc`, `puncture_proc`, `crit_tier`, and so on); effects do not use a generic `target` field. An attack's intrinsic `forced_procs` distribution remains part of its attack data. Form applicability also uses `when`, such as `{"when": "incarnon_form"}`; there is no separate scope language.

All proc producers feed one status model. Normal status rolls, intrinsic and effect-provided forced procs, conditional damage procs, and capped random procs contribute to expected proc counts, DoT, non-damaging status stacks, unique-status counts, and effects triggered by status events. Random procs are distributed across the 13 physical and elemental status types; a capped `random_proc` effect such as Secondary Encumber contributes at most one additional proc per simultaneous attack.

Runtime state retains the value supplied by the caller. Each effect applies its own stack cap during resolution.

Compatibility metadata only produces warnings. Automatic `when` conditions define where an effect actually applies.

Upgrades whose mechanics are not modeled remain available for inspection with `upgrade.implemented == False`. Configuring one emits `UnimplementedUpgradeWarning`, preserves it in the build, and excludes its effects from calculated results.

## Calculation coverage

The engine includes ranged and melee rates, charge/burst/reload/battery cycles, Incarnon charge pools and form-conditioned evolutions, elemental ordering, additive and multiplicative Condition Overload, status uptime and stack windows, forced procs, damage-over-time effects, first/last magazine mixtures, nested attack trees, stance and combo calculations, falloff-averaged damage, AoE and punch-through damage density, special arcane/mod behaviors, enemy scaling and defenses, hit zones, and removal/Shapley contribution analysis.

`average` and `final` include the average falloff multiplier in ordinary per-hit and attack-tree damage. `effective.instantaneous_fire_rate` is the mechanical firing rate, `effective.attack_event_rate` and `average.sustained_fire_rate` account for the complete firing cycle, and `effective.reload_time` is a duration in seconds. AoE and punch-through mass calculations live in the separate `density` result pool.

Attacks with falloff expose `average.falloff_multiplier`. AoE attacks also expose a falloff-weighted spherical `density.damage_mass` in cubic meters; attacks with punch through and a finite range expose a linear mass in meters. `density.damage_density` and `density.damage_density_per_second` multiply pre-falloff damage by that mass, representing expected aggregate damage at a uniform target density of one target per cubic meter or meter respectively. They do not multiply the already falloff-averaged `final` pool, so falloff is counted only once.

Ranged attacks may provide `max_range`; falloff end is used when no distinct maximum is available. Punch-through density uses sliding hit pairs across that finite range. `density.falloff_multiplier` is the normalized sliding-pair result and `density.damage_mass` is `max_range * density.falloff_multiplier`. Punch-through without falloff uses a multiplier of one. Density remains unavailable when no finite range can be established.

## Isolated validation

Run from this directory:

```bash
python -m pip install -e .
python -P -B -m unittest discover -s tests -v
```

The suite validates direct construction, effect-channel boundaries, repositories, all 656 weapons, all 779 upgrades against primary/secondary/melee engines, all 877 enemies, every selectable evolution and attack, and fixed combat-parity scenarios.
