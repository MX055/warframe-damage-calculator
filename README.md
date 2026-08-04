# Warframe Damage Calculator

An analytic Python damage calculator for Warframe weapons.

## Basic use

```python
from warframe_damage_calculator import Calculator, Build, State, arsenal

weapon = arsenal.primary.get("Phenmor")
target = arsenal.enemy.get("Heavy Gunner").set(level=200, steel_path=True)

build = Build(
    mods=[
        arsenal.mod.get("Galvanized Chamber"),
        arsenal.mod.get("Critical Delay"),
    ],
    perks=[
        arsenal.perk.get("Elemental Excess"),
        arsenal.perk.get("Devouring Attrition"),
    ],
)

calculator = Calculator(weapon, target, build)
result = calculator.resolve(attack="incarnon_form", body_part="head")
print(result.aggregate.damage.total_dps)
```

`Weapon` and `Enemy` are definitions. `Build` owns selected mods, arcanes, and global evolution perks. `Calculator` owns one weapon-target-build combination, while attack selection, body-part selection, and temporary state belong to each calculation:

```python
result = calculator.resolve(attack="heavy_attack", body_part="head", state=State(combo_multiplier=12))
```

`State` accepts only `combo_multiplier`, `stance_combo`, and `ability_strength`. When `combo_multiplier` is omitted, melee combo-scaling mods and heavy damage use the attack’s modded `initial_combo` hits converted with `floor(hits / 20) + 1`, capped by the weapon’s `max_combo`. Perk `when` conditions are not part of `State`; set them with `perk.set(...)` or `build.set(...)` (defaulting to active / max stacks), the same way as other upgrade runtime fields.

## Custom definitions

Definition types are available directly from the package root, so custom content does not depend on internal module paths:

```python
from warframe_damage_calculator import Attack, AttackStats, Calculator, Compatibility, Dist, Effect, GeneratedAttack, Inheritance, Build, Mod, Primary, RelatedAttacks, Source, UpgradeStats

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
        generated_attack=GeneratedAttack(
            name="Aftershock",
            parent=RelatedAttacks(names=["shot"]),
            inheritance=Inheritance(
                include=["trigger", "delivery", "form", "category"],
                override={
                    "aoe": True,
                    "stats.damage.heat": {"source": "$parent.stats.damage.total", "multiplier": 0.1},
                    "stats.falloff.end_range": 2,
                },
            ),
        ),
    ),
)
result = Calculator(weapon, build=Build(mods=[mod])).resolve()
```

### Per-value rank scaling

Upgrade ranks scale individual numeric values, not complete effect entries.

**Effect `value` fields** scale by default. A plain number is treated as max-rank and scales down with rank. Fixed effect values must opt out:

```json
{"value": 0.2, "rank_scale": false}
```

A plain effect value is enough when scaling is wanted (`"value": 0.9`), so an explicit `{"value": 0.9, "rank_scale": true}` wrapper is unnecessary.

**All other scaled numbers** (automatic `chance` / `for` / `stacks`, source `multiplier`, effect `for`, nested generated-attack numbers) do **not** scale by default. A plain number stays fixed. Opt in with an explicit wrapper:

```json
{"value": 0.3, "rank_scale": true}
```

`rank_scale` affects only the numeric value directly wrapped by `{ "value": ..., "rank_scale": ... }`. It is not interpreted recursively and must not wrap mappings, lists, attacks, source expressions, or complete stat entries. For a source expression, wrap only the numeric parameter that scales:

```json
{
  "source": "$parent.stats.damage.total",
  "multiplier": {"value": 0.3, "rank_scale": true}
}
```

That means resolved parent damage × rank-scaled multiplier. The resolved parent value itself is not scaled again.

Generated attacks do not have an entry-level `rank_scale` flag.

The formula converts a maximum-rank encoded value into the selected-rank value:

```text
factor = (rank + 1) / (max_rank + 1)
proportional / flat / base: encoded_value * factor
multiplicative: 1 + (encoded_value - 1) * factor
```

Rank scaling is resolved once when an upgrade is loaded for its selected rank. Generated-attack construction then uses already-resolved numbers.

The database schema version is `28`.

### Generated attacks

Weapon attacks use `Attack`. Upgrade-generated attacks use a separate `GeneratedAttack` record under `stats.generated_attack`:

```json
{
  "name": "Melee Duplicate",
  "parent": {"deliveries": ["melee"]},
  "inheritance": {
    "include": ["trigger", "delivery", "aoe", "form", "category", "stats"]
  },
  "automatic": {
    "on": "near_yellow_critical_hit",
    "chance": {"value": 1, "rank_scale": true}
  }
}
```

`parent` is a `RelatedAttacks` selector (`names`, `triggers`, `deliveries`, `forms`, `categories`, `aoe`) and exists only on generated attacks. `children` is a list of display names on both weapon attacks and generated attacks (for example `["Rocket Explosion"]` or a self-name for recursion). `$parent` is the lexical reference to the selected parent during inheritance and expression resolution. Generated attacks inherit nothing by default.

A generated attack that lists itself in `children` is a recursive self-trigger. The tree walk does not expand that cycle; expected contribution is folded analytically as the geometric series `p + p² + p³ + … = p / (1 - p)` for trigger chance `p < 1`.

`inheritance.include` is an allowlist of exact top-level or nested paths to deep-copy, such as `trigger` or `stats.damage.heat`. `inheritance.exclude` removes paths after include (so `include=["stats"]` with `exclude=["stats.forced_procs"]` works). Wildcard inheritance is not supported. Explicit values live under `inheritance.override` as a flat path→value map (for example `"aoe": true` or `"stats.falloff.end_range": 20`). Override paths use the same path rules as include/exclude and must not nest under one another. After include/exclude, override paths are expanded into a nested attack definition and deep-merged over inherited mappings; scalars and lists replace. Dynamic source expressions are resolved after inheritance and use complete paths such as `$parent.stats.damage.total`; `default` supplies a value when an optional source path is absent.

`automatic` controls activation and averaged occurrence:

- `when`: event that activates a timed or conditional effect
- `chance`: probability of activation when `when`/`on` occurs
- `on`: one event or a list of events that produce the effect while eligible (`hit`, `critical_hit`, `non_critical_hit`, `near_yellow_critical_hit`, or typed `*_status_proc` events for generated attacks)
- `for`: duration
- `refresh`: whether another activation refreshes duration

Typed status events such as `heat_status_proc` expose their status type to the generated-attack resolver. Multiple `on` events combine expected rates without inventing an independent status-chance roll for the generated attack.

Melee Duplicate lists every gameplay field it copies explicitly and does not declare `children`, so a duplicated hit cannot reproduce native secondary attacks or recursively duplicate itself. Trigger chance scales linearly to 100% at max rank. No damage value is rank-scaled:

```json
{
  "name": "Melee Duplicate",
  "parent": {"deliveries": ["melee"]},
  "inheritance": {
    "include": ["trigger", "delivery", "aoe", "form", "category", "stats"]
  },
  "automatic": {
    "on": "near_yellow_critical_hit",
    "chance": {"value": 1, "rank_scale": true}
  }
}
```
Melee Influence is represented through the same generated-attack pipeline as an expected-value abstraction, not as a literal independent random attack. It inherits elemental damage and forced-proc fields plus crit and Condition Overload inputs. Activation chance is fixed (`"chance": 0.2`). Duration scales with rank (`"for": {"value": 18, "rank_scale": true}` → 3 at rank 0, 18 at rank 5). Range stays a fixed `20` because the in-game 10→20 progression does not match the project's linear rank formula. `"hits_source": false` excludes Influence from single-target aggregate damage and status: in-game it only applies elemental melee statuses to other enemies in range, not the hit that triggered it. The Influence attack still reports per-nearby-target DoT and spatial mass so crowd metrics can value it. The `automatic.on` list of elemental status-proc events drives the averaged occurrence rate; Influence does not roll status chance again:

```json
{
  "name": "Melee Influence",
  "parent": {"deliveries": ["melee"]},
  "inheritance": {
    "include": [
      "trigger", "delivery", "form", "category",
      "stats.crit_chance", "stats.crit_damage", "stats.co_factor", "stats.co_effect",
      "stats.damage.heat", "stats.damage.cold", "stats.damage.electricity", "stats.damage.toxin",
      "stats.damage.blast", "stats.damage.radiation", "stats.damage.gas", "stats.damage.magnetic",
      "stats.damage.viral", "stats.damage.corrosive",
      "stats.forced_procs.heat", "stats.forced_procs.cold", "stats.forced_procs.electricity",
      "stats.forced_procs.toxin", "stats.forced_procs.blast", "stats.forced_procs.radiation",
      "stats.forced_procs.gas", "stats.forced_procs.magnetic", "stats.forced_procs.viral",
      "stats.forced_procs.corrosive"
    ],
    "override": {
      "aoe": true,
      "hits_source": false,
      "stats.falloff.start_range": 0,
      "stats.falloff.end_range": 20,
      "stats.falloff.final_multiplier": 1
    }
  },
  "automatic": {
    "when": "electricity_status_proc",
    "chance": 0.2,
    "on": ["heat_status_proc", "cold_status_proc", "electricity_status_proc", "toxin_status_proc", "blast_status_proc", "radiation_status_proc", "gas_status_proc", "magnetic_status_proc", "viral_status_proc", "corrosive_status_proc"],
    "for": {"value": 18, "rank_scale": true},
    "refresh": false
  }
}
```

Because the calculator averages status events rather than simulating individual random procs, the Influence contribution uses the complete eligible elemental payload gated by the electricity activation chance. It does not correlate each typed status event to only that type's damage slice. That expected-value limitation is intentional and documented by tests.

Nightwatch Napalm is an independently calculated child. Only the heat damage multiplier scales with rank (`0.05` at rank 0 through `0.3` at rank 5). Radius stays 90% of the parent explosion radius. `multishot: 5` encodes the expected linger tick applications, not ordinary multishot that other mods should modify. Crit, status, forced Heat, and Condition Overload behavior are explicit:

```json
{
  "name": "Nightwatch Napalm Linger",
  "parent": {"names": ["Rocket Explosion"]},
  "inheritance": {
    "include": ["trigger", "delivery", "form", "category"],
    "override": {
      "aoe": true,
      "stats.damage.heat": {"source": "$parent.stats.damage.total", "multiplier": {"value": 0.3, "rank_scale": true}},
      "stats.forced_procs.heat": 1,
      "stats.falloff.start_range": 0,
      "stats.falloff.end_range": {"source": "$parent.stats.falloff.end_range", "multiplier": 0.9},
      "stats.falloff.final_multiplier": 1,
      "stats.crit_chance": 0,
      "stats.crit_damage": 0,
      "stats.status_chance": 0,
      "stats.multishot": 5,
      "stats.co_factor": 1,
      "stats.co_effect": "adds"
    }
  }
}
```

Generated attacks retain the generating upgrade and selected parent as provenance. Generic parent selectors do not select upgrade-generated attacks; selecting one requires its explicit generated-attack key. This prevents Melee Influence, Melee Duplicate, and Nightwatch Napalm from generating themselves. Rank-resolved values are not scaled again during attack construction. The same root API exposes `Arcane`, `Perk`, `PerkValues`, `Effect`, `Source`, `Inheritance`, `GeneratedAttack`, `RelatedAttacks`, `Combo`, `Automatic`, `UpgradeValue`, `Falloff`, all concrete weapon categories, and the enemy definition types. Calculation-result models and optimizer implementation details remain in their dedicated modules.

Stance mods store combos by stable id with an explicit `type`:

```json
"combos": {
  "morning_sun": {
    "type": "neutral",
    "name": "Morning Sun",
    "multiplier": 2.2,
    "hits": 10,
    "duration": 4.25
  }
}
```

```python
Mod(..., combos={"morning_sun": Combo(type="neutral", name="Morning Sun", multiplier=2.2, hits=10, duration=4.25)})
```

## Global perks

Perks are loaded independently of weapons:

```python
perk = arsenal.perk.get("Devouring Attrition")
```

A global `Perk` is an identity marker: `description` is `"$description"` and `stats` is `"$stats"`. A weapon evolution choice stores the concrete upgrade-style effects, for example `{"status_chance": [{"value": 0.2, "mode": "flat", "automatic": {}}]}`. Zero-valued effects are omitted. At resolve time those weapon effects become the perk’s resolved effects directly—there is no global template slot list and no explicit `default: 0` source fill-in. Custom definitions use the same shorthand on `Perk`, with concrete values supplied via `PerkValues`.

```text
global Perk markers + weapon PerkValues -> ResolvedPerk -> effect pipeline
```

The same perk name can resolve to different values on different weapons:

```python
perk = arsenal.perk.get("Elemental Balance")
telos = arsenal.primary.get("Telos Boltor").resolve_perk(perk)
prime = arsenal.primary.get("Boltor Prime").resolve_perk(perk)
```

Every selected item in `Build.perks` is resolved through the weapon before calculation. A perk not available on the weapon raises an error. Selecting a perk at the wrong list index for its tier (1-based: `perks[i]` should be tier `i+1`) or selecting two perks of the same tier emits a `PerkCompatibilityWarning`; the wrong-position perk still pairs with that perk’s weapon values, and for duplicate tiers the first selection is kept. Tier and choice data are retained in `weapon.perk_choices` (keyed by perk name within each tier) for selection and optimizer search spaces; calculation does not convert selected perks back into database instructions. Conditional perk effects use defaults from the weapon’s concrete effects (`True` or max stacks), with overrides via `perk.set(...)` / `build.set(...)`.

## Result navigation

Results expose aggregate totals and per-attack metric groups:

```python
result.aggregate.damage.total_dps
result.aggregate.status
```

The attack scope is one individual component:

```python
projectile = result.attacks["air_burst_projectile"]
projectile.base
projectile.modded
projectile.effective
projectile.upgrades
projectile.perks
projectile.damage
projectile.critical
projectile.timing
projectile.status
projectile.spatial
```

`result.selected_attack` identifies the selected root. `result.attacks.keys()` lists the components included in its final damage. Aggregate results intentionally do not expose a combined critical chance or other meaningless cross-component weapon stats.

Damage and timing metrics live on each attack’s `damage` / `timing` groups. Critical averages live on `critical`, including weak-point parallels such as `weak_point_crit_chance`. Spatial mass fields are present only for AoE components (`spatial.damage_mass` is `None` otherwise). Body-part selection is made at resolve time via `body_part=...`; zones on the enemy definition use `normal`, `weak_point`, and `resistant`.

Each available damage pool exposes:

```python
direct_dph
dot_dph
total_dph
direct_dps
dot_dps
total_dps
```

## Repeated calculations

A calculator keeps one build fixed while allowing repeated attack and body-part calculations:

```python
calculator = Calculator(weapon, target, build)
body = calculator.resolve(attack="incarnon_form", body_part="body")
head = calculator.resolve(attack="incarnon_form", body_part="head")
```

Each result records its selected attack and body part. Build optimizers can reuse the lower-level calculation engine without changing this public API.

## OptimizationResult

On Python 3.14, the default metric is evaluated across up to four isolated interpreter workers. Candidate order, evaluation count, scores, and tie-breaking remain deterministic; parallelism changes only how independent scores in each search batch are calculated. Use `workers=1` for sequential execution if you need more stable wall times.

```python
optimized = Optimizer(calculator).resolve(attack="rocket_impact", body_part="body")
```

The optional `state` argument has the same meaning and validation as `Calculator.resolve()` and is applied to every candidate, for example `state=State(combo_multiplier=12, stance_combo="heavy")` for an appropriate melee weapon. Use `workers=1` for sequential execution or set an explicit positive worker count to match the available CPU and memory.

`spatial` controls how damage mass enters search scoring and is separate from the metric:

- `"auto"` (default) — run one dual-metric search that scores every candidate for both single-target (`mass = 1`) and AoE (full damage mass), track both bests, then pick the build with the larger relative advantage under its own scorer
- `"full"` — score with each attack's damage mass; matches the default contributions metric
- `"none"` — ignore damage mass (treat mass as 1)

`"auto"` shares pools and seeds in one dual-metric search, then runs phased specialist climbs (single-target half, then AoE half) so each objective gets dedicated local/perturbation/rebuild depth instead of mixed sources. The evaluation budget is a ceiling, not a quota: search fanout (pools, seeds, sources) scales with `sqrt(requested_evaluations / 5000)`. Auto uses the same requested evaluation ceiling as a dedicated pass — dual scoring still updates both single-target and AoE bests from each component calculation. Contributions still default to the full-mass balanced metric. The resolved mode is reported on `OptimizationResult.spatial` as `"full"` or `"none"` (never `"auto"`).

Custom full-result metrics (`metric=callable`) stay sequential because arbitrary callables and full result objects cannot safely be transferred between isolated interpreters. Metrics that can score from the compact component tuple `(direct_dph, dot_dph, direct_dps, dot_dps, damage_mass)` can keep the parallel path by passing `compact_metric=...`. The default metric uses `balanced_damage_components` automatically. Prefer a top-level or otherwise picklable callable (for example `functools.partial` of a module function) so worker interpreters can import it:

```python
from warframe_damage_calculator import Optimizer, balanced_damage_components

optimized = Optimizer(calculator).resolve(compact_metric=balanced_damage_components)
```

## Contributions

Contribution analysis is part of the calculator workflow and includes selected upgrades, evolution perks, and progenitor bonuses:

```python
calculator = Calculator(weapon, target, build)
contributions = calculator.contributions(attack="incarnon_form", body_part="weak_point")

removal = contributions.removal
contribution = contributions.contribution
```

Build contribution percentages are leave-one-out removal differences normalized to sum to 1 (a component that does not change the metric gets 0%). The default metric is `balanced_damage_metric`, the same score the optimizer uses by default. Pass `metric="total_dps"` or another aggregate damage field name for a simpler metric, or any callable of a `CalculationResult`. `body_part` selects an enemy body-part key such as `"body"` or `"head"`. A dotted path may select another result value.

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
spatial.total_dph_mass
spatial.total_dps_mass
```

The `_mass` suffix and dimension distinguish these values from ordinary damage.

## Formatting

Formatting is separate from definitions and calculation:

```python
from warframe_damage_calculator import Formatter
from warframe_damage_calculator.formatting.objects import format_build, format_perk, format_upgrade, format_weapon
from warframe_damage_calculator.formatting.results import format_result

print(format_weapon(weapon))
print(format_upgrade(build.upgrades[0]))
print(format_perk(build.perks[0]))
print(format_build(build))
print(format_result(result))
print(Formatter(result).stat_summary())
print(Formatter(result).build_summary())
print(Formatter(result).status_summary())
```
