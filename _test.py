from warframe_damage_calculator import *


weapon = Secondary(crit_chance=1.5).configure(Upgrade(secondary_enervate=6))

print(weapon.stats.average_secondary_enervate_bonus)
