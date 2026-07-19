from warframe_damage_calculator import Build, Upgrade, arsenal


def main() -> None:
    weapon = arsenal.get("Corinth Prime")
    mod1 = Upgrade({"context": {"name": "Riven"}, "stats": {"impact": -0.886, "crit_damage": 0.855, "multishot": 1.126, "crit_chance": 0.887}})
    mod2 = arsenal.get("Galvanized Hell")
    mod3 = arsenal.get("Semi-Shotgun Cannonade")
    mod4 = arsenal.get("Hunter Munitions")
    mod5 = arsenal.get("Primed Chilling Grasp")
    mod6 = arsenal.get("Primed Ravage")
    mod7 = arsenal.get("Critical Delay")
    mod8 = arsenal.get("Toxic Barrage")
    exilus = arsenal.get("Vigilante Supplies")
    arcane = arsenal.get("Primary Merciless")
    buff = Upgrade({"context": {"name": "Buff"}, "stats": {"flat_crit_damage": 1.2}})
    build = Build(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, exilus, arcane, buff)
    weapon.configure(build)

    print(weapon.format.summary())
    

if __name__ == "__main__":
    main()
