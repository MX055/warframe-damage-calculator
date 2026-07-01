from warframe_damage_calculator import *

def main():
    weapon = Primary(damage_dist=dist(impact=25.2, puncture=37.8, slash=27), fire_rate=1.42, reload_speed=3.00, magazine_capacity=20, multishot=6.00, crit_chance=0.30, crit_damage=2.80, status_chance=0.09)
    mod1 = Upgrade(damage_dist=dist(impact=-0.886), crit_damage=0.855, multishot=1.126, crit_chance=0.887)
    mod2 = Upgrade(multishot=1.10 + 0.30*4)
    mod3 = Upgrade(base_damage=2.40)
    mod4 = Upgrade(hunter_munitions=0.30)
    mod5 = Upgrade(damage_dist=dist(cold=1.65))
    mod6 = Upgrade(crit_damage=1.10)
    mod7 = Upgrade(crit_chance=2.00)
    mod8 = Upgrade(damage_dist=dist(toxin=0.60), status_chance=0.60)
    mod9 = Upgrade(vigilante_bonus=0.05)
    arcane = Upgrade(base_damage=0.30*12, reload_speed=0.30)
    buffs = Upgrade(flat_crit_damage=1.20)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, mod9, arcane, buffs)

    print(weapon.format.summary())

if __name__ == "__main__":
    main()