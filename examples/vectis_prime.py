from warframe_damage_calculator import Build, Calculator, Formatter, arsenal


weapon = arsenal.primary.get("Vectis Prime")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
build = Build(
    mods=[
        arsenal.mod.get("Primed Chamber"),
        arsenal.mod.get("Galvanized Aptitude"),
        arsenal.mod.get("Critical Delay")
    ],
    perks=[
        arsenal.perk.get("Incarnon Transmutation"),
        arsenal.perk.get("Inciting Incident"),
        arsenal.perk.get("Rapid Reinforcement"),
        arsenal.perk.get("Critical Parallel"),
    ]
)
calculator = Calculator(weapon, target, build)
result = calculator.resolve(body_part="head")

formatter = Formatter(result)
print(formatter.stat_summary())
print(formatter.damage_summary())
print(formatter.build_summary())
