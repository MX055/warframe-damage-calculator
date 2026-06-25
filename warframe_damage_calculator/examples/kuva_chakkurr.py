from warframe_damage_calculator import *

def main():
    galvanized_scope_condition = 1
    galvanized_scope_stacks = 5
    bladed_rounds_condition = 1
    primary_deadhead_stacks = 3
    
    weapon = ranged(base_damage_dist=dist(impact=260), base_explosion_damage_dist=dist(slash=29, puncture=52, blast=25), forced_procs=dist(impact=1), base_fire_rate=1.17, base_reload_speed=3.3, base_magazine_capacity=11, base_multishot=1.0, base_crit_chance=0.50, base_crit_damage=2.3, base_status_chance=0.27)
    mod1 = upgrade(internal_bleeding=0.35)
    mod2 = upgrade(crit_damage=1.20)
    mod3 = upgrade(crit_chance=1.20*galvanized_scope_condition + 0.40*galvanized_scope_stacks)
    mod4 = upgrade(multiplicative_weakpoint_crit_chance=3.50, weakpoint_damage=3.50)
    mod5 = upgrade(crit_damage=1.20*bladed_rounds_condition)
    mod6 = upgrade(base_damage=2.40)
    mod7 = upgrade(crit_chance=2.00)
    mod8 = upgrade(damage_dist=dist(cold=1.65))
    mod9 = upgrade(vigilante_bonus=0.05)
    element = upgrade(damage_dist=dist(heat=0.574))
    arcane = upgrade(base_damage=1.20*primary_deadhead_stacks, weakpoint_damage=0.30)
    buffs = upgrade(flat_crit_damage=1.2)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, mod9, element, arcane, buffs)

    print(weapon.summary())

if __name__ == "__main__":
    main()