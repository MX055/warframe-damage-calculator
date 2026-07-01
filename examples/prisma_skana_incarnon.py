from warframe_damage_calculator import *

def main():
    weapon = Melee(damage_dist=dist(slash=189, impact=40.5, puncture=40.5), crit_chance=0.53, crit_damage=2.20, status_chance=0.16, attack_speed=1.00)
    mod1 = Upgrade(crit_chance=2.75)
    mod2 = Upgrade(base_damage=1.375)
    mod3 = Upgrade(status_damage=0.80, status_chance=0.30*4)
    mod4 = Upgrade(damage_dist=dist(electricity=0.60), status_chance=0.60)
    mod5 = Upgrade(crit_chance=2.217, base_damage=1.669, crit_damage=1.049, damage_dist=dist(slash=-1.063))
    mod6 = Upgrade(crit_damage=0.90)
    mod7 = Upgrade(status_chance=0.90)
    mod8 = Upgrade(damage_dist=dist(electricity=0.90))
    buffs = Upgrade(flat_crit_damage=1.20, attack_speed=0.70, base_damage=0.70)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, buffs)

    print(weapon.format.summary())

if __name__ == "__main__":
    main()