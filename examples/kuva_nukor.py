from warframe_damage_calculator import *

def main():
    weapon = Secondary(damage_dist=dist(radiation=21), crit_chance=0.07, crit_damage=5.00, status_chance=0.50, fire_rate=10, reload_speed=2.00, magazine_capacity=77, is_beam=True)
    mod1 = Upgrade(multishot=1.10 + 0.30*4)
    mod2 = Upgrade(base_damage=2.20)
    mod3 = Upgrade(base_damage=1.65)
    mod4 = Upgrade(fire_rate=0.60, multishot=0.60)
    mod5 = Upgrade(crit_damage=1.10)
    mod6 = Upgrade(damage_dist=dist(heat=0.90))
    mod7 = Upgrade(crit_damage=0.45)
    mod8 = Upgrade(crit_damage=0.60, base_damage=-0.15)
    arcane = Upgrade(secondary_enervate=6)
    element = Upgrade(damage_dist=dist(heat=0.49))
    buffs = Upgrade(flat_crit_damage=1.20)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, arcane, element, buffs)
    
    print(weapon.format.summary())

if __name__ == "__main__":
    main()