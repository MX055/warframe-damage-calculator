from warframe_damage_calculator import *

def main():
    weapon = Primary(damage_dist=dist(impact=260), forced_procs=dist(impact=1.00), explosion_damage_dist=dist(slash=29, puncture=52, blast=25), explosion_forced_procs=dist(impact=1.00), crit_chance=0.50, crit_damage=2.30, status_chance=0.27, fire_rate=1.17, reload_speed=3.30, magazine_capacity=11)
    mod1 = Upgrade(internal_bleeding=0.35)
    mod2 = Upgrade(crit_damage=1.20)
    mod3 = Upgrade(crit_chance=1.20 + 0.40*5)
    mod4 = Upgrade(weakpoint_damage=3.50, multiplicative_weakpoint_crit_chance=3.50, multishot_lock=True)
    mod5 = Upgrade(crit_damage=1.20)
    mod6 = Upgrade(base_damage=2.40, fire_rate_lock=True)
    mod7 = Upgrade(crit_chance=2.00, fire_rate=-0.20)
    mod8 = Upgrade(damage_dist=dist(cold=1.65))
    mod9 = Upgrade(vigilante_bonus=0.05)
    arcane = Upgrade(base_damage=1.20*3, weakpoint_damage=0.30)
    element = Upgrade(damage_dist=dist(heat=0.574))
    buffs = Upgrade(flat_crit_damage=1.20)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, mod9, arcane, element, buffs)
    
    print(weapon.format.summary())

if __name__ == "__main__":
    main()