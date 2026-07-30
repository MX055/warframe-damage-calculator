from warframe_damage_calculator import Calculator, Loadout, ResultFormatter, arsenal


weapon = arsenal.weapon.get("Corinth Prime")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
loadout = Loadout(
    upgrades=[
        arsenal.upgrade.get("Galvanized Hell"),
        arsenal.upgrade.get("Critical Deceleration"),
        arsenal.upgrade.get("Primed Ravage")
    ]
)
calculator = Calculator(weapon, target)
result = calculator.calculate(loadout)
formatter = ResultFormatter(result)
print(formatter.summary())
print(result.aggregate.final.normal.total_dps)
