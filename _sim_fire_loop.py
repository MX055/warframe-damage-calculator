from random import randint, random
from math import ceil

is_beam = randint(0, 1)
is_battery = randint(0, 1)
burst_count = randint(1, 5)
ammo_efficiency = 1 - (1 - random()) / (2 if is_beam else 1)
max_mag_size = burst_count * randint(1, 10)
recharge_rate = random() * 39 + 1
reload_speed = random() * 4 + 1 + (max_mag_size / recharge_rate if is_battery else 0)
charge_time = random() * 1.5
burst_delay = random() * 0.1
fire_rate = random() * 19.5 + 0.5
pc_bonus = random() * 100

rounds = 0
seconds = 0
pc_shots = 0
mag = max_mag_size

for _ in range(1_000_000):
    seconds += charge_time

    rounds += 1
    pc_shots += (pc_bonus if ceil(mag) == max_mag_size else 0)
    mag += ammo_efficiency - 1

    for _ in range(burst_count - 1):
        seconds += burst_delay

        rounds += 1
        pc_shots += (pc_bonus if ceil(mag) == max_mag_size else 0)
        mag += ammo_efficiency - 1

    if mag <= 0:
        seconds += reload_speed
        mag = max_mag_size
    else:
        seconds += 1 / fire_rate

sim_rps = rounds / seconds
sim_pc = pc_shots / rounds

cal_rps = max_mag_size / (max_mag_size / burst_count * (charge_time + (burst_count - 1) * burst_delay) + (max_mag_size / burst_count - (1 - ammo_efficiency)) / fire_rate + (1 - ammo_efficiency) * reload_speed)
cal_pc = pc_bonus / max_mag_size

print(sim_pc)
print(cal_pc)
print(sim_rps)
print(cal_rps)