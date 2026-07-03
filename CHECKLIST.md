# Feature Checklist

## Documentation
- [ ] Add docstrings.

## Weapons
- [x] Primary weapons.
- [x] Secondary weapons.
- [x] Melee weapons (light attacks).
- [x] Beam weapon support.
- [x] Hitscan weapon support.
- [ ] Projectile falloff.

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

## Status Effects
- [x] Status chance.
- [x] Status damage.
- [x] Expected status proc calculation.
- [x] Hunter Munitions.
- [x] Internal Bleeding (Hemorrhage).
- [x] Secondary Encumber.
- [ ] Heat armor strip.
- [ ] Slash dots ignore armor.
- [ ] Corrosive armor strip.
- [ ] Viral damage to health.
- [ ] Magnetic damage to shields and overguard.

## Fire Control
- [x] Fire rate.
- [x] Reload speed.
- [x] Magazine size.
- [x] Multishot.
- [x] Ammo efficiency.
- [x] Charge weapons.
- [x] Battery weapons.
- [ ] Burst-fire weapons.
- [ ] Ammo consumption per shot

## Weapon Effects
- [x] Primed Chamber / Charged Chamber.
- [x] Vigilante Set bonus.
- [x] Melee Duplicate.
- [x] Melee Doughty.
- [x] Secondary Enervate.
- [x] Secondary Encumber.
- [ ] Automatic Condition Overload bonus.

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
- [ ] Damage contribution percentages.

## API
- [x] Upgrade system.
- [x] Build class.
- [x] Damage distribution class.
- [x] Dataclass-based weapon definitions.
- [ ] Build import/export.

## Testing
- [x] Unit tests.
- [ ] Increase edge-case coverage.
- [ ] Performance benchmarks.

# Assumptions

- If **Hunter Munitions** and **Internal Bleeding** trigger simultaneously, only the higher-damage proc is applied. *(Source: Wiki)*
- **Secondary Encumber** scales with total damage, status damage, faction damage, and critical damage. *(Source: None)*
- **Secondary Encumber** can trigger **Hemorrhage** (*Internal Bleeding*). *(Source: None)*
- **Secondary Encumber** can trigger at most once per shot. *(Source: Wiki)*
- *burst daleay* is affected by *fire rate* *(Source: None)*
- *burst delay* is not affected by negative *fire rate* *(Source: Wiki)*
- *charge time* is affected by *fire rate* *(Source: Wiki)*
- *recharge rate* is not affected by *reload speed* *(Source: Wiki)*
- *beam weapons* only consume 0.5 ammo per tick *(Source: Wiki)*
- Weapon firing cycles are assumed to work as follows. *(Source: Testing)*

```text
[ammo per shot] <-  (1 - [ammo efficiency]) / (2 if [is beam] else 1)
[effective reload time] <- [reload time] + ([magazine capacity] / [recharge rate] if [is battery] else 0)
[bullet count] <- [magazine capacity]

repeat
    wait [charge time] seconds
    [bullet count] <- [bullet count] - [ammo per shot]
    for i in range [burst count]:
        wait [burst dalay] seconds
        [bullet count] <- [bullet count] - [ammo per shot]
    if [bullet count] = 0
        wait [effective reload time] seconds
        [bullet count] <- [magazine capacity]
    else
        wait 1 / [fire rate] seconds
```

