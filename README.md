# Warframe Damage Calculator

An analytic Python damage calculator for Warframe weapons.

## Basic use

```python
from warframe_damage_calculator import Calculator, Loadout, State, arsenal

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
result = calculator.resolve(attack="heavy_attack", body_part="head", state=State(combo_multiplier=12))
```

`State` accepts only `combo_multiplier`, `stance_combo`, and `ability_strength`. When `combo_multiplier` is omitted, melee combo-scaling mods and heavy damage use the attack’s modded `initial_combo` hits converted with `floor(hits / 20) + 1`, capped by the weapon’s `max_combo`. Perk `when` conditions are not part of `State`; set them with `perk.set(...)` or `loadout.set(...)` (defaulting to active / max stacks), the same way as other upgrade runtime fields.

## Custom definitions

Definition types are available directly from the package root, so custom content does not depend on internal module paths:

```python
from warframe_damage_calculator import Attack, AttackStats, Calculator, Compatibility, Dist, Effect, Inheritance, Links, Loadout, Mod, Primary, RelatedAttacks, Source, UpgradeStats

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
        generated_attack=Attack(
            name="Aftershock",
            aoe=True,
            inheritance=Inheritance(include=["trigger", "delivery", "form", "category"]),
            links=Links(parents=RelatedAttacks(names=["shot"])),
            stats={
                "damage": {"heat": {"source": "$parent.stats.damage.total", "multiplier": 0.1}},
                "falloff": {"end_range": 2},
            },
        ),
    ),
)
result = Calculator(weapon, loadout=Loadout(mods=[mod])).resolve()
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

The database schema version is `24`.

### Generated attacks

Weapon attacks and upgrade-generated attacks share one `Attack` record. A generated attack is stored flat under `stats.generated_attack` (no `kind` / `parent` / `attack` envelope):

```json
{
  "name": "Melee Duplicate",
  "inheritance": {
    "include": ["trigger", "delivery", "aoe", "form", "category", "stats"]
  },
  "links": {
    "parents": {"deliveries": ["melee"]}
  },
  "automatic": {
    "on": "near_yellow_critical_hit",
    "chance": {"value": 1, "rank_scale": true}
  }
}
```

`links.parents` and `links.children` are each an optional `RelatedAttacks` selector (`names`, `triggers`, `deliveries`, `forms`, `categories`, `aoe`). Multiple targets are listed on the selector axes (for example `names: ["Initial Blast", "Bubble Collapse"]`). Display names are preferred in `names`; weapon map keys stay stable ids. `$parent` is the lexical reference to the selected parent during inheritance and expression resolution. Generated attacks inherit nothing by default.

A generated attack that lists itself in `links.children` is a recursive self-trigger. The tree walk does not expand that cycle; expected contribution is folded analytically as the geometric series `p + p² + p³ + … = p / (1 - p)` for trigger chance `p < 1`.

`inheritance.include` is an allowlist of exact top-level or nested paths to deep-copy, such as `trigger` or `stats.damage.heat`. `inheritance.exclude` removes paths after include (so `include=["stats"]` with `exclude=["stats.forced_procs"]` works). Wildcard inheritance is not supported. Explicit values merge recursively over inherited mappings, while explicit scalars and lists replace inherited values. Dynamic source expressions are resolved after inheritance and use complete paths such as `$parent.stats.damage.total`; `default` supplies a value when an optional source path is absent.

Native weapon attacks store child relationships as `links.children` (typically `{"names": ["Rocket Explosion"]}`) instead of a top-level `children` key.

`automatic` controls activation and averaged occurrence:

- `when`: event that activates a timed or conditional effect
- `chance`: probability of activation when `when`/`on` occurs
- `on`: one event or a list of events that produce the effect while eligible (`hit`, `critical_hit`, `non_critical_hit`, `near_yellow_critical_hit`, or typed `*_status_proc` events for generated attacks)
- `for`: duration
- `refresh`: whether another activation refreshes duration

Typed status events such as `heat_status_proc` expose their status type to the generated-attack resolver. Multiple `on` events combine expected rates without inventing an independent status-chance roll for the generated attack.

Melee Duplicate lists every gameplay field it copies explicitly and does not inherit `links`, so a duplicated hit cannot reproduce native secondary attacks or recursively duplicate itself. Trigger chance scales linearly to 100% at max rank. No damage value is rank-scaled:

```json
{
  "name": "Melee Duplicate",
  "inheritance": {
    "include": ["trigger", "delivery", "aoe", "form", "category", "stats"]
  },
  "links": {
    "parents": {"deliveries": ["melee"]}
  },
  "automatic": {
    "on": "near_yellow_critical_hit",
    "chance": {"value": 1, "rank_scale": true}
  }
}
```
Melee Influence is represented through the same generated-attack pipeline as an expected-value abstraction, not as a literal independent random attack. It inherits elemental damage and forced-proc fields plus crit and Condition Overload inputs. Activation chance is fixed (`"chance": 0.2`). Duration scales with rank (`"for": {"value": 18, "rank_scale": true}` → 3 at rank 0, 18 at rank 5). Range stays a fixed `20` because the in-game 10→20 progression does not match the project's linear rank formula. The `automatic.on` list of elemental status-proc events drives the averaged occurrence rate; Influence does not roll status chance again:

```json
{
  "name": "Melee Influence",
  "aoe": true,
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
    ]
  },
  "links": {
    "parents": {"deliveries": ["melee"]}
  },
  "stats": {"falloff": {"start_range": 0, "end_range": 20, "final_multiplier": 1}},
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
  "aoe": true,
  "inheritance": {
    "include": ["trigger", "delivery", "form", "category"]
  },
  "links": {
    "parents": {"names": ["Rocket Explosion"]}
  },
  "stats": {
    "damage": {"heat": {"source": "$parent.stats.damage.total", "multiplier": {"value": 0.3, "rank_scale": true}}},
    "forced_procs": {"heat": 1},
    "falloff": {
      "start_range": 0,
      "end_range": {"source": "$parent.stats.falloff.end_range", "multiplier": 0.9},
      "final_multiplier": 1
    },
    "crit_chance": 0,
    "crit_damage": 0,
    "status_chance": 0,
    "multishot": 5,
    "co_factor": 1,
    "co_effect": "adds"
  }
}
```

Generated attacks retain the generating upgrade and selected parent as provenance. Generic parent selectors do not select upgrade-generated attacks; selecting one requires its explicit generated-attack key. This prevents Melee Influence, Melee Duplicate, and Nightwatch Napalm from generating themselves. Rank-resolved values are not scaled again during attack construction. The same root API exposes `Arcane`, `Perk`, `PerkValues`, `Effect`, `Source`, `Inheritance`, `Links`, `RelatedAttacks`, `Combo`, `Automatic`, `UpgradeValue`, `Falloff`, all concrete weapon categories, and the enemy definition types. Calculation-result models and optimizer implementation details remain in their dedicated modules.

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

A global `Perk` owns the complete effect template: affected stats, modes, families, conditions, automatic behavior, and `$values` source expressions. A weapon owns a `PerkValues` entry containing the concrete values referenced by those expressions. Custom definitions use `Source("$values.stat_name[0]")` for the same representation.

```text
global Perk template + weapon PerkValues -> ResolvedPerk -> effect pipeline
```

The same template can resolve to different values:

```python
perk = arsenal.perk.get("Elemental Balance")
telos = arsenal.primary.get("Telos Boltor").resolve_perk(perk)
prime = arsenal.primary.get("Boltor Prime").resolve_perk(perk)
```

Every selected item in `Loadout.evolutions` is resolved through the weapon before calculation. Missing values, unknown values, duplicate tier selections, and perks unavailable to the weapon are rejected. Tier and choice data are retained in `weapon.perk_choices` for selection and optimizer search spaces; calculation does not convert selected perks back into database instructions. Conditional perk effects use perk runtime (`perk.set(...)` / `loadout.set(...)`) with defaults of `True` or max stacks, matching ranked upgrades.

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

The optional `state` argument has the same meaning and validation as `Calculator.resolve()` and is applied to every candidate, for example `state=State(combo_multiplier=12, stance_combo="heavy")` for an appropriate melee weapon. Use `workers=1` for sequential execution or set an explicit positive worker count to match the available CPU and memory. Custom callable metrics remain sequential because arbitrary callables and full result objects cannot safely be transferred between isolated interpreters.

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
