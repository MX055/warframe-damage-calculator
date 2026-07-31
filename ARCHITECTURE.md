# Architecture

## Dependency direction

```text
domain
  ↑
engine
  ↑
```

The domain layer contains concrete definitions and result value objects. The engine imports those concrete types directly. No protocol mirrors `Weapon`, `Attack`, `Loadout`, runtime state, status records, or result records.

## Ownership

```text
Arsenal
├── weapon definitions
├── upgrade definitions
├── global perk templates
└── enemy definitions

Weapon
├── attack definitions
├── weapon-specific PerkValues
├── perk tier/choice metadata
└── immutable calculation defaults

Loadout
├── selected upgrades
└── selected global perks

Calculator
├── weapon
└── target
```

`Weapon` owns no loadout, target, mutable selection, result, formatter, or optimizer state.

## Perk resolution

Global templates are authoritative:

```text
arsenal.perk.get(name)
        ↓
Perk
  stat identity
  mode and family
  conditions
  automatic behavior
  placeholder positions
        +
Weapon.perks[perk]
  concrete values only
        ↓
ResolvedPerk
        ↓
CalculationContext
```

Every weapon record supplies one concrete value for every placeholder and no unknown value. Named perks whose source records contain multiple mechanical variants use a universal template containing those positions; an inapplicable position receives a zero value. This keeps all effect metadata global while preserving weapon-specific mechanics and numerical behavior.

Tier and choice metadata live in `weapon.perk_choices`. They validate mutually exclusive selections and support search-space generation, but the engine consumes `ResolvedPerk` objects rather than tier-choice instruction mappings.

## Calculation flow

```text
Weapon + Target + Loadout + selected attack + explicit state
        ↓
resolve selected perks
        ↓
CalculationContext
        ↓
resolve upgrade and evolution effects
        ↓
calculate preliminary attack components
        ↓
construct the shared analytic status model
        ↓
calculate final components
        ↓
fold descendant damage into the aggregate
        ↓
CalculationResult
```

`CalculationContext` is internal and contains only the concrete inputs required by the engine. It does not imitate the public `Weapon` interface.

## Result scopes

`CalculationResult` has two distinct scopes:

- `result.aggregate` represents the selected root and all descendants. It exposes aggregate final damage, aggregate status, component names, and per-component spatial outputs.
- `result.attacks[name]` represents one attack component. It exposes definition, base, modded, effective, upgrade, evolution, average, final, status, spatial, child-name, and original-damage pools.

Canonical damage navigation is:

```python
result.aggregate.average.normal.total_dps
result.attacks[name].average.normal.total_dps
```

The aggregate scope deliberately has no critical chance, multishot, or other cross-component statistic.

## Spatial boundary

Ordinary damage is independent of assumed density, spacing, equivalent extent, and arbitrary target limits. AoE components may expose dimensional analytic damage mass. Punch through remains a mechanical stat and is not converted into a target multiplier.

## Analysis and formatting

Contribution resolution is part of the engine and evaluates configured loadouts through `Calculator`. It includes upgrades, selected perks, and progenitor bonuses. Formatting consumes definition and result objects and never belongs to `Weapon`.

## Optimizer boundary

`PreparedCalculator` caches validated attack-tree selection for repeated evaluations. Candidate configuration remains one `Loadout`; transient combat state remains an explicit calculation argument.
