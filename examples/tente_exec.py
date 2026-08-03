from warframe_damage_calculator import Build, Progenitor, Calculator, Formatter, arsenal


weapon = arsenal.melee.get("Tenet Exec")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
build = Build(
    mods=[
        arsenal.mod.get("Rending Crane"),
        arsenal.mod.get("Galvanized Steel"),
        arsenal.mod.get("Primed Pressure Point")
    ],
    arcanes=[
        arsenal.arcane.get("Melee Duplicate")
    ],
    progenitor=Progenitor(element="electricity", bonus=0.60)
)
calculator = Calculator(weapon, target, build)
result = calculator.resolve(attack="heavy_slam_attack", state={"stance_combo": "heavy"})

formatter = Formatter(result)
print(formatter.stat_summary())
print(formatter.status_summary())
print(formatter.build_summary())
