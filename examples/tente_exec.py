from warframe_damage_calculator import Loadout, Progenitor, Calculator, Formatter, arsenal


weapon = arsenal.melee.get("Tenet Exec")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
loadout = Loadout(
    mods=[
        arsenal.mod.get("Rending Crane"),
        arsenal.mod.get("Galvanized Steel"),
        arsenal.mod.get("Primed Pressure Point")
    ],
    arcanes=[
        arsenal.arcane.get("Melee Duplicate")
    ],
    progenitor=Progenitor("electricity", 0.60)
)
calculator = Calculator(weapon, target, loadout)
result = calculator.resolve(attack="heavy_slam_attack", state={"stance_combo": "heavy"})

formatter = Formatter(result)
print(formatter.summary())
print(formatter.contributions())
