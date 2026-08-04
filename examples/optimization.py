from warframe_damage_calculator import Build, Calculator, Optimizer, Formatter, arsenal, State


weapon = arsenal.melee.get("Prisma Skana")
target = arsenal.enemy.get("Exo Gokstad Officer").set(level=235, steel_path=True)
build = Build()

calculator = Calculator(weapon, target, build)
optimizer = Optimizer(calculator)
state = State(stance_combo="forward")
optimized = optimizer.resolve(body_part="body", state=state)
formatter = Formatter(optimized.result)

print(formatter.stat_summary())
print(formatter.damage_summary())
print(formatter.build_summary())



weapon = arsenal.primary.get("Kuva Ogris")
target = arsenal.enemy.get("Exo Gokstad Officer").set(level=235, steel_path=True)
build = Build()

calculator = Calculator(weapon, target, build)
optimizer = Optimizer(calculator)
optimized = optimizer.resolve(body_part="body")
formatter = Formatter(optimized.result)

print(formatter.stat_summary())
print(formatter.damage_summary())
print(formatter.build_summary())





