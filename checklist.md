# Feature Checklist

- Add docstrings.

# Assumption Checklist

- If **Hunter Munitions** and **Internal Bleeding** trigger simultaneously, only the higher-damage proc is applied. *(Source: Wiki)*
- **Secondary Encumber** scales with total damage, status damage, faction damage, and critical damage. *(Source: None)*
- **Secondary Encumber** can trigger **Hemorrhage** (*Internal Bleeding*). *(Source: None)*
- **Secondary Encumber** can trigger at most once per shot. *(Source: Wiki)*
- Weapon firing cycles are assumed to work as follows. *(Source: Testing)*

```text
wait [charge time] seconds
[bullet count] <- [bullet count] + [ammo efficiency] - 1
if [bullet count] = 0
    wait [reload time] seconds
    [bullet count] <- [mag size]
else
    wait 1 / [fire rate] seconds
repeat
```
