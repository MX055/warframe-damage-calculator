from warframe_damage_calculator import *

def main():
    weapon = Secondary(damage_dist=dist(slash=40.5, impact=27, puncture=67.5), crit_chance=0.31, crit_damage=3.00, status_chance=0.43, fire_rate=4.5, reload_speed=0.00, magazine_capacity=270)
    mod1 = Upgrade(multishot=1.10 + 0.30*4)
    mod2 = Upgrade(base_damage=2.20)
    mod3 = Upgrade(crit_chance=2.00, fire_rate=-0.20)
    mod4 = Upgrade(status_chance=0.80, base_damage=0.40*3)
    mod5 = Upgrade(crit_chance=2.718, crit_damage=1.1624)
    mod6 = Upgrade(damage_dist=dist(radiation=0.60), fire_rate=0.40)
    mod7 = Upgrade(crit_damage=1.10)
    mod8 = Upgrade(fire_rate=0.90, base_damage=-0.15)
    trait = Upgrade(multiplicative_fire_rate=1.50, ammo_efficiency=1.00, damage_dist=dist(toxin=1.00))
    buffs = Upgrade(flat_crit_damage=1.20)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, trait, buffs)

    print(weapon.format.summary())

if __name__ == "__main__":
    main()