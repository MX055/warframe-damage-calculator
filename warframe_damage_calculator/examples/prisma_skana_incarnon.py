from warframe_damage_calculator import *

def main():
    weapon = melee(base_damage_dist=dist(impact=40.5, puncture=40.5, slash=189), base_attack_speed=1.0, base_crit_chance=0.53, base_crit_damage=2.2, base_status_chance=0.16)
    mod1 = upgrade(crit_chance=2.75)
    mod2 = upgrade(base_damage=1.375)
    mod3 = upgrade(status_chance=1.20, status_damage=0.80)
    mod4 = upgrade(damage_dist=dist(electricity=0.60), status_chance=0.60)
    mod5 = upgrade(damage_dist=dist(slash=-1.063), base_damage=1.669, crit_chance=2.217, crit_damage=1.049)
    mod6 = upgrade(crit_damage=0.90)
    mod7 = upgrade(status_chance=0.90)
    mod8 = upgrade(damage_dist=dist(electricity=0.90))
    buffs = upgrade(base_damage=0.70, attack_speed=0.70, flat_crit_damage=1.2)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, buffs)

    print(weapon.summary())

if __name__ == "__main__":
    main()