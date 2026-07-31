from warframe_damage_calculator import Calculator, Loadout, ResultFormatter, arsenal


weapon = arsenal.primary.get("Phenmor")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
loadout = Loadout(
    upgrades=[
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
result = calculator.calculate(attack="incarnon_form", bodypart="body")
formatter = ResultFormatter(result)
print(formatter.summary())
print(formatter.contributions())