from warframe_damage_calculator import *

def main():
    galvanized_chamber_stacks = 5
    galvanized_aptitude_stacks = 2
    primary_merciless_satcks = 12
    
    weapon = ranged(base_damage_dist=dist(impact=44), base_explosion_damage_dist=dist(slash=10.6, puncture=42.4), base_fire_rate=10, base_reload_speed=1.6, base_magazine_capacity=48, base_multishot=1.0, base_crit_chance=0.34, base_crit_damage=3.0, base_status_chance=0.18)
    mod1 = upgrade(base_damage=1.65)
    mod2 = upgrade(crit_chance=1.056, crit_damage=0.869, reload_speed=-0.136)
    mod3 = upgrade(damage_dist=dist(toxin=0.60), status_chance=0.60)
    mod4 = upgrade(damage_dist=dist(cold=0.60), status_chance=0.60)
    mod5 = upgrade(multishot=0.80 + 0.30*galvanized_chamber_stacks)
    mod6 = upgrade(multiplicative_base_damage=0.40*galvanized_aptitude_stacks, status_chance=0.80)
    mod7 = upgrade(crit_damage=1.20)
    mod8 = upgrade(crit_chance=2.00, fire_rate=-0.20)
    mod9 = upgrade(vigilante_bonus=0.05)
    arcane = upgrade(base_damage=0.30*primary_merciless_satcks, reload_speed=0.30)
    buffs = upgrade(flat_crit_damage=1.2)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, mod9, arcane, buffs)

    print(weapon.summary())

if __name__ == "__main__":
    main()