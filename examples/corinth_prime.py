from warframe_damage_calculator import Loadout, Calculator, Formatter, arsenal


weapon = arsenal.primary.get("Corinth Prime")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
loadout = Loadout(
    mods=[
        arsenal.mod.get("Galvanized Hell"),
        arsenal.mod.get("Critical Deceleration"),
        arsenal.mod.get("Primed Ravage")
    ]
)
calculator = Calculator(weapon, target, loadout)
result = calculator.resolve()

formatter = Formatter(result)
print(formatter.summary())
print(formatter.contributions())
