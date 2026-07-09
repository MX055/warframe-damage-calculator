from warframe_damage_calculator import *


def main():
    weapon = db.get_weapon("Corinth Prime")
    mod1 = Upgrade(damage_dist=dist(impact=-0.886), crit_damage=0.855, multishot=1.126, crit_chance=0.887, name="riven")
    mod2 = db.get_upgrade("Galvanized Hell")
    mod3 = db.get_upgrade("Semi-Shotgun Cannonade")
    mod4 = db.get_upgrade("Hunter Munitions")
    mod5 = db.get_upgrade("Primed Chilling Grasp")
    mod6 = db.get_upgrade("Primed Ravage")
    mod7 = db.get_upgrade("Critical Deceleration")
    mod8 = db.get_upgrade("Toxic Barrage")
    mod9 = db.get_upgrade("Vigilante Supplies")
    arcane = db.get_upgrade("Primary Merciless")
    buffs = Upgrade(flat_crit_damage=1.20, name="buff")
    build = Build(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, mod9, arcane, buffs)
    weapon.configure(build)

    print(weapon.format.upgrades())

if __name__ == "__main__":
    main()