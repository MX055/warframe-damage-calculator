from warframe_damage_calculator import *

mod = Mod(
    name="Example Recursive Mod",
    description="Placeholder",
    slot_type="regular_mod",
    max_rank=2,
    compatibility=Compatibility(subtypes=["rifle"]),
    stats=UpgradeStats(
        generated_attack=GeneratedAttack(
            name="Generated Attack",
            parent=RelatedAttacks(names=["Normal Attack"]),
            children=["Generated Attack"],
            inheritance=Inheritance(
                include=["trigger", "delivery", "form", "category", "stats"],
                exclude=["stats.forced_procs"],
                override={
                    "aoe": True,
                    "stats.forced_procs": {"source": "stats.damage.slash", "multilplier": 0.1},
                    "stats.falloff.start_range": 5,
                    "stats.falloff.end_range": 10,
                    "stats.falloff.final_multiplier": 0.5,
                },
            ),
            automatic=Automatic(on="impact_status_proc")
        )
    )
)

weapon = arsenal.primary.get("Karak")
target = arsenal.enemy.get("Corrupted Heavy Gunner").set(level=100)
build = Build(mods=[mod])

calculator = Calculator(weapon, target, build)
result = calculator.resolve()
formatter = Formatter(result)

print(formatter.stat_summary())
print(formatter.damage_summary())
print(formatter.build_summary())
