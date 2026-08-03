from warframe_damage_calculator import Build, Calculator, Optimizer, Formatter, arsenal, State


weapon = arsenal.melee.get("Prisma Skana")
target = arsenal.enemy.get("Exo Gokstad Officer").set(level=235, steel_path=True)
build = Build()

calculator = Calculator(weapon, target, build)
optimizer = Optimizer(calculator)

optimized = optimizer.resolve(body_part="body", state=State(stance_combo="forward"))
print(optimized.elapsed)
formatter = Formatter(optimized.result)

print(formatter.stat_summary())
print(formatter.status_summary())
print(formatter.build_summary())









