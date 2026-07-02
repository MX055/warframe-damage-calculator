# Feature Checklist

## Documentation
- [ ] Add docstrings.
- [ ] Expand the README with additional usage examples.
- [ ] Document the assumptions and limitations of the damage model.

## Weapons
- [x] Primary weapons.
- [x] Secondary weapons.
- [x] Melee weapons (light attacks).
- [x] Beam weapon support.
- [x] Hitscan weapon support.
- [ ] Projectile flight time.
- [ ] Projectile falloff.
- [ ] Explosive radial damage.
- [ ] Incarnon transformations.
- [ ] Exalted weapons.

## Damage
- [x] Physical damage.
- [x] Elemental damage.
- [x] Combined elemental damage.
- [x] IPS weighting.
- [x] Base damage modifiers.
- [x] Multiplicative base damage.
- [x] Faction damage.
- [x] Weakpoint damage.
- [x] Critical damage.
- [x] Critical chance.
- [x] Flat critical chance bonuses.
- [x] Flat critical damage bonuses.
- [x] Multiplicative critical chance.
- [x] Weakpoint critical chance.
- [x] Multiplicative weakpoint critical chance.
- [ ] Damage attenuation.
- [ ] Enemy armor, health, and shields.
- [ ] Armor stripping.
- [ ] Damage vulnerability.
- [ ] Body-part damage modifiers.

## Status Effects
- [x] Status chance.
- [x] Status damage.
- [x] Expected status proc calculation.
- [x] Hunter Munitions.
- [x] Internal Bleeding (Hemorrhage).
- [x] Secondary Encumber.
- [ ] Individual status effect simulation.
- [ ] Status duration.
- [ ] Status refresh mechanics.
- [ ] Heat armor strip.
- [ ] Slash bleed scaling.
- [ ] Electric chaining.
- [ ] Gas clouds.
- [ ] Blast stagger.
- [ ] Magnetic shield interactions.
- [ ] Corrosive armor strip.
- [ ] Viral health amplification.

## Fire Control
- [x] Fire rate.
- [x] Reload speed.
- [x] Magazine size.
- [x] Multishot.
- [x] Ammo efficiency.
- [x] Charge weapons.
- [ ] Burst-fire weapons.
- [ ] Battery weapons.
- [ ] Spin-up weapons.

## Weapon Effects
- [x] Primed Chamber / Charged Chamber.
- [x] Vigilante Set bonus.
- [x] Melee Duplicate.
- [ ] Galvanized Aptitude-style scaling.
- [ ] Condition Overload.
- [ ] GunCO mechanics.
- [ ] Punch Through.
- [ ] Ricochets.
- [ ] Infinite body punch-through interactions.

## Calculations
- [x] Flat damage per hit (DPH).
- [x] Flat damage per second (DPS).
- [x] DoT damage per hit (DOTPH).
- [x] DoT damage per second (DOTPS).
- [x] Total damage per hit.
- [x] Total damage per second.
- [x] Effective fire rate.
- [x] Expected status procs per shot.
- [ ] Time-to-kill (TTK).
- [ ] Sustained DPS against enemies.
- [ ] Damage breakdown by source.
- [ ] Damage contribution percentages.

## API
- [x] Upgrade system.
- [x] Build class.
- [x] Damage distribution class.
- [x] Dataclass-based weapon definitions.
- [ ] Build serialization.
- [ ] Build import/export.
- [ ] JSON schema validation.

## Testing
- [x] Unit tests.
- [ ] Increase edge-case coverage.
- [ ] Property-based tests.
- [ ] Performance benchmarks.
- [ ] Continuous integration.

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
