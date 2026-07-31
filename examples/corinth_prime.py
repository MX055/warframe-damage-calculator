from warframe_damage_calculator import Calculator, Loadout, ResultFormatter, arsenal


weapon = arsenal.primary.get("Corinth Prime")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
loadout = Loadout(
    upgrades=[
        arsenal.mod.get("Galvanized Hell"),
        arsenal.mod.get("Critical Deceleration"),
        arsenal.mod.get("Primed Ravage")
    ]
)
calculator = Calculator(weapon, target, loadout)
result = calculator.calculate()
formatter = ResultFormatter(result)
print(formatter.summary())
print(formatter.contributions())