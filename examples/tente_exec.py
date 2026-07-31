from warframe_damage_calculator import Calculator, Loadout, ResultFormatter, Progenitor, arsenal


weapon = arsenal.weapon.get("Tenet Exec")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
loadout = Loadout(
    upgrades=[
        arsenal.upgrade.get("Rending Crane"),
        arsenal.upgrade.get("Galvanized Steel"),
        arsenal.upgrade.get("Primed Pressure Point"),
        arsenal.upgrade.get("Melee Duplicate")
    ],
    progenitor=Progenitor("electricity", 0.60)
)
calculator = Calculator(weapon, target, loadout)
result = calculator.calculate(attack="heavy_slam_attack", bodypart="body", state={"stance_combo": "heavy"})
formatter = ResultFormatter(result)
print(formatter.summary())
print(formatter.contributions())