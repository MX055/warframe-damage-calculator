from warframe_damage_calculator import *

mod = Mod(
    name="Example Recursive Mod",
    description="Placeholder",
    slot="regular_mod",
    max_rank=2,
    compatibility=Compatibility(subtypes=["rifle"]),
    stats=UpgradeStats(
        generated_attack=Attack(
            name="Generated Attack",
            aoe=True,
            inheritance=Inheritance(
                include=[
                    "trigger",
                    "delivery",
                    "form",
                    "category",
                    "stats"
                ],
                exclude=[
                    "stats.forced_procs"
                ],
            ),
            stats=AttackStats(
                falloff=Falloff(5, 10, 0.5)
            ),
            links=Links(
                parents=RelatedAttacks(names=["Normal Attack"]),
                children=RelatedAttacks(names=["Generated Attack"]),
            ),
            automatic=Automatic(
                on="impact_status_proc"
            )
        )
    )
)

weapon = arsenal.primary.get("Karak")
target = arsenal.enemy.get("Corrupted Heavy Gunner").set(level=100)
loadout = Loadout(mods=[mod])

calculator = Calculator(weapon, target, loadout)
result = calculator.resolve()
formatter = Formatter(result)

print(formatter.summary())
print(formatter.contributions())