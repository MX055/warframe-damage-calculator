from warframe_damage_calculator import Loadout, Calculator, Formatter, arsenal


weapon = arsenal.primary.get("Vectis Prime")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
loadout = Loadout(
    mods=[
        arsenal.mod.get("Primed Chamber"),
        arsenal.mod.get("Galvanized Aptitude"),
        arsenal.mod.get("Critical Delay")
    ],
    evolutions=[
        arsenal.perk.get("Incarnon Transmutation"),
        arsenal.perk.get("Inciting Incident"),
        arsenal.perk.get("Rapid Reinforcement"),
        arsenal.perk.get("Critical Parallel"),
    ]
)
calculator = Calculator(weapon, target, loadout)
body = calculator.resolve()
head = calculator.resolve(body_part="head")

print(Formatter(body).summary())
print(Formatter(head).contributions())
