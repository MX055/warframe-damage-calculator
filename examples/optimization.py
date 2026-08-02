from warframe_damage_calculator import Loadout, Calculator, Optimizer, Formatter, arsenal


weapon = arsenal.melee.get("Prisma Skana")
target = arsenal.enemy.get("Exo Gokstad Officer").set(level=235, steel_path=True)
loadout = Loadout()

calculator = Calculator(weapon, target, loadout)
optimizer = Optimizer(calculator)

optimized = optimizer.resolve(body_part="body")
print(optimized.summary["elapsed"])
formatter = Formatter(optimized.result)

print(formatter.summary())
print(formatter.contributions())









