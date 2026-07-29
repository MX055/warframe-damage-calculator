from warframe_damage_calculator import Build, arsenal


def main() -> None:
    mod1 = arsenal.upgrade.get("Galvanized Hell").set(on_kill=4),
    mod2 = arsenal.upgrade.get("Critical Deceleration"),
    mod3 = arsenal.upgrade.get("Primed Ravage"),
    mod4 = arsenal.upgrade.get("Hunter Munitions"),
    mod5 = arsenal.upgrade.get("Primed Chilling Grasp"),
    mod6 = arsenal.upgrade.get("Toxic Barrage"),
    build = Build(mod1, mod2, mod3, mod4, mod5, mod6)
    target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
    weapon = arsenal.weapon.get("Corinth Prime").set(attack="air_burst_projectile")
    weapon.configure(build, target)

    print(weapon.format.summary())


if __name__ == "__main__": main()
