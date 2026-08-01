from warframe_damage_calculator import Loadout, Calculator, Optimizer, Formatter, arsenal


weapon = arsenal.primary.get("Kuva Ogris")
target = arsenal.enemy.get("Exo Gokstad Officer").set(level=235, steel_path=True)
loadout = Loadout()

calculator = Calculator(weapon, target, loadout)
optimizer = Optimizer(calculator)

optimized = optimizer.resolve(body_part="body")
formatter = Formatter(optimized.result)

print(formatter.summary())
print(formatter.contributions())