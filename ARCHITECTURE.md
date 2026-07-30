# Rewrite architecture

This directory is a self-contained implementation. It does not import, load files from, execute, or require the original `warframe_damage_calculator` package.

The package uses three directional layers:

1. `domain`: concrete weapon, upgrade, enemy, damage, effect, and result values.
2. `engine`: per-attack calculation, weapon-tree orchestration, effect resolution, aggregation, evolutions, status, damage, targets, attack trees, and contributions.
3. package API: repositories, configuration, formatting, and public exports.

Domain objects contain definition and caller-managed runtime state. Engine-managed combat conditions never enter public runtime state; they are evaluated from the automatic effect dictionary inside the engine.

Calculation is a staged pipeline:

1. resolve rank and caller-managed manual conditions;
2. select and scope evolution effects;
3. compute pre-damage scalars and sustained status acquisition;
4. evaluate engine-managed automatic conditions;
5. aggregate common stats and multiplicative families;
6. construct effective damage, crit, status, rates, ammunition, and melee state;
7. apply target pools, defenses, bodyparts, direct damage, and status damage;
8. mix magazine-position classes through the shared zone-damage path and fold the selected attack tree;
9. expose per-attack and final metrics without wrapper objects.

Automatic status acquisition is deliberately non-recursive: a bonus produced from sustained status stacks does not feed back into the status model that produced it. This keeps Condition Overload and stack effects deterministic.

The package owns its models, engine, repositories, schema-v9 database, formatters, tests, documentation, and packaging. The bundled catalog is initialized lazily, so importing domain utilities does not parse the full database. Its isolated test workflow installs the package before running with Python's safe-path option.
