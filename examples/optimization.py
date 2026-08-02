from warframe_damage_calculator import Loadout, Calculator, Optimizer, Formatter, arsenal


weapon = arsenal.primary.get("Kuva Ogris")
target = arsenal.enemy.get("Exo Gokstad Officer").set(level=235, steel_path=True)
loadout = Loadout()

calculator = Calculator(weapon, target, loadout)
optimizer = Optimizer(calculator)

optimized = optimizer.resolve(body_part="body")
print(optimized.summary["elapsed"], optimized.result.aggregate.average.total_dps)


weapon = arsenal.primary.get("Vectis Prime")
target = arsenal.enemy.get("Exo Gokstad Officer").set(level=235, steel_path=True)
loadout = Loadout()

calculator = Calculator(weapon, target, loadout)
optimizer = Optimizer(calculator)

optimized = optimizer.resolve(body_part="head")
print(optimized.summary["elapsed"])








