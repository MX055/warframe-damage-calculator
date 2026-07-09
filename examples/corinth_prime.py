from warframe_damage_calculator import *


def main():
    weapon = load_primary("Corinth Prime")
    mod1 = Upgrade(damage_dist=dist(impact=-0.886), crit_damage=0.855, multishot=1.126, crit_chance=0.887)
    mod2 = load_mod("Galvanized Hell", stacks=4)
    mod3 = load_mod("Semi-Shotgun Cannonade")
    mod4 = load_mod("Hunter Munitions")
    mod5 = load_mod("Primed Chilling Grasp")
    mod6 = load_mod("Primed Ravage")
    mod7 = load_mod("Critical Deceleration")
    mod8 = load_mod("Toxic Barrage")
    mod9 = load_mod("Vigilante Supplies")
    arcane = load_arcane("Primary Merciless", stacks=12)
    buffs = Upgrade(flat_crit_damage=1.20)
    build = Build(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, mod9, arcane, buffs)
    weapon.configure(build)

    print(weapon.format.summary())

if __name__ == "__main__":
    main()