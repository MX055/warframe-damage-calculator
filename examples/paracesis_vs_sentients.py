from warframe_damage_calculator import *

def main():
    weapon = Melee(damage_dist=dist(slash=155.4, impact=48.8, puncture=17.8), crit_chance=0.31, crit_damage=2.60, status_chance=0.22, attack_speed=0.917)
    mod1 = Upgrade(crit_chance=2.75, faction_damage=0.70)
    mod2 = Upgrade(base_damage=1.375, faction_damage=0.70)
    mod3 = Upgrade(damage_dist=dist(electricity=0.90))
    mod4 = Upgrade(crit_damage=0.90)
    mod5 = Upgrade(attack_speed=0.55)
    mod6 = Upgrade(crit_damage=0.417, crit_chance=0.877, damage_dist=dist(heat=0.442))
    mod7 = Upgrade(base_damage=1.00, attack_speed=-0.20)
    arcane = Upgrade(melee_duplicate=1.00)
    trait = Upgrade(faction_damage=0.60)
    buffs = Upgrade(flat_crit_damage=1.20, attack_speed=0.70, base_damage=0.70)
    weapon.configure(mod1, mod2, mod3, mod4, mod5, mod6, mod7, arcane, trait, buffs)

    print(weapon.format.summary())

if __name__ == "__main__":
    main()