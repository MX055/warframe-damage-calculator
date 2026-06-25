from warframe_damage_calculator import *

def main():
    galvanized_hell_stacks = 4
    primary_merciless_satcks = 12
    
    weapon = ranged(base_damage_dist=dist(impact=25.2, puncture=37.8, slash=27), base_fire_rate=1.42, base_reload_speed=3.00, base_magazine_capacity=20, base_multishot=6, base_crit_chance=0.30, base_crit_damage=2.80, base_status_chance=0.09)
    mod1 = upgrade(damage_dist=dist(impact=-0.886), crit_damage=0.855, multishot=1.126, crit_chance=0.887)
    mod2 = upgrade(multishot=1.10 + 0.30*galvanized_hell_stacks)
    mod3 = upgrade(base_damage=2.40)
    mod4 = upgrade(hunter_munitions=0.30)
    mod5 = upgrade(damage_dist=dist(cold=1.65))
    mod6 = upgrade(crit_damage=1.10)
    mod7 = upgrade(crit_chance=2.00)
    mod8 = upgrade(damage_dist=dist(toxin=0.60), status_chance=0.60)
    mod9 = upgrade(vigilante_bonus=0.05)
    arcane = upgrade(base_damage=0.30*primary_merciless_satcks, reload_speed=0.30)
    buffs = upgrade(flat_crit_damage=1.2)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, mod9, arcane, buffs)

    print(weapon.summary())

if __name__ == "__main__":
    main()