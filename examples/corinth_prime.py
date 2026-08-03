from warframe_damage_calculator import Build, Calculator, Formatter, arsenal


weapon = arsenal.primary.get("Corinth Prime")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
build = Build(
    mods=[
        arsenal.mod.get("Galvanized Hell"),
        arsenal.mod.get("Critical Deceleration"),
        arsenal.mod.get("Primed Ravage")
    ]
)
calculator = Calculator(weapon, target, build)
result = calculator.resolve()

formatter = Formatter(result)
print(formatter.stat_summary())
print(formatter.status_summary())
print(formatter.build_summary())
