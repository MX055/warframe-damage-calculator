import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from warframe_damage_calculator import Build, arsenal


def main() -> None:
    build = Build(
        arsenal.upgrade.get("Galvanized Hell").set(on_kill=4),
        arsenal.upgrade.get("Critical Deceleration"),
        arsenal.upgrade.get("Primed Ravage"),
        arsenal.upgrade.get("Hunter Munitions"),
        arsenal.upgrade.get("Primed Chilling Grasp"),
        arsenal.upgrade.get("Toxic Barrage"),
    )
    target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
    weapon = arsenal.weapon.get("Corinth Prime").set(attack="air_burst_projectile")
    weapon.configure(build, target)

    print(weapon.format.summary())


if __name__ == "__main__": main()
