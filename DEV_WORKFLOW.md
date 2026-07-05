# Development Workflow

## Design Rules

- Utils should contain common constants or functions.
- Weapon models should contain almost no logic.
- Calculators perform all computations.
- Formaters only format the output.
- Fileds only store base stats data.
- States only store weapon data.
- All the variables must be typed.

## Add a Weapon Stat

1. Add the stat to the appropriate field model.
2. Add the stat to the corresponding state with its neutral default value.
3. Add the corresponding Moded stat to the appropriate calculator.
4. Add the corresponding Effective stat to the calculator.
5. Incorporate the Effective stat into the relevant damage formulas (or create a new formula if necessary).
6. Verify all affected damage formulas still produce the expected results.
7. Update documentation if the public API changed.

## Add an Upgrade Stat

1. Add the stat to the upgrade model with a default value of `0`.
2. Add the stat to the corresponding state with its neutral default value.
3. Incorporate the Build stat into the appropriate Moded stat calculations (creating a new Moded stat if necessary).
4. Incorporate the Moded stat into the appropriate Effective stat calculations if needed (creating a new Effective stat if necessary).
5. Incorporate the Effective stat into the relevant damage formulas of needed (or create a new formula if necessary).
6. Verify all affected damage formulas still produce the expected results.
7. Update documentation if the public API changed.
