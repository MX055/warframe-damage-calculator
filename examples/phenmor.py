from warframe_damage_calculator import Loadout, Progenitor, Calculator, Formatter, arsenal


weapon = arsenal.primary.get("Phenmor")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
loadout = Loadout(
    mods=[
        arsenal.mod.get("Galvanized Chamber"),
        arsenal.mod.get("Galvanized Aptitude"),
        arsenal.mod.get("Primed Cryo Rounds")
    ],
    evolutions=[
        arsenal.perk.get("Incarnon Transmutation"),
        arsenal.perk.get("Void's Guidance"),
        arsenal.perk.get("Retribution's Vessel"),
        arsenal.perk.get("Elemental Excess"),
        arsenal.perk.get("Devouring Attrition")
    ]
)
calculator = Calculator(weapon, target, loadout)
result = calculator.resolve(attack="incarnon_form", body_part="body")
formatter = Formatter(result)
print(formatter.summary())
print(formatter.contributions())
