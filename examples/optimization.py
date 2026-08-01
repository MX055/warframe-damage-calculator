from warframe_damage_calculator import Loadout, Calculator, Optimizer, Formatter, arsenal


weapon = arsenal.primary.get("Vectis Prime")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
loadout = Loadout()

calculator = Calculator(weapon, target, loadout)
optimizer = Optimizer(calculator)


optimized = optimizer.resolve()
formatter = Formatter(optimized.result)

print(formatter.summary())
print(formatter.contributions())