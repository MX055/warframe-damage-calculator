from warframe_damage_calculator import Calculator, Loadout, ResultFormatter, arsenal


weapon = arsenal.weapon.get("Phenmor")
target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
loadout = Loadout(
    upgrades=[
        arsenal.upgrade.get("Galvanized Chamber"),
        arsenal.upgrade.get("Galvanized Aptitude"),
        arsenal.upgrade.get("Primed Cryo Rounds")
    ],
    evolutions=[
        arsenal.perk.get("Incarnon Transmutation"),
        arsenal.perk.get("Void's Guidance"),
        arsenal.perk.get("Retribution's Vessel"),
        arsenal.perk.get("Elemental Excess"),
        arsenal.perk.get("Devouring Attrition")
    ]
)
calculator = Calculator(weapon, target)
result = calculator.calculate(loadout, attack="incarnon_form")
formatter = ResultFormatter(result)
print(formatter.summary())
print(formatter.contributions())