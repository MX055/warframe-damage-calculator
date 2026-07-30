from warframe_damage_calculator import *

def build_riven() -> Upgrade:
    return Upgrade(
        name="Riven", 
        kind="mod", 
        slot="normal",
        max_rank=8,
        compatibility=Compatibility(names=["Corinth Prime"]), 
        stats=UpgradeStats(
            impact=Effect(properties={"value": -0.886}),
            crit_damage=Effect(properties={"value": 0.855}),
            multishot=Effect(properties={"value": 1.126}),
            crit_chance=Effect(properties={"value": 0.887})
        )
    )

def build_buff() -> Upgrade:
    return Upgrade(
        name="Buff",
        kind="buff",
        slot="buff",
        stats=UpgradeStats(
            crit_damage=Effect(properties={"value": 1.2, "mode": "flat"})
        )
    )


def main() -> None:
    weapon: Primary = arsenal.weapon.get("Corinth Prime")
    mod1 = build_riven()
    mod2 = arsenal.upgrade.get("Galvanized Hell")
    mod3 = arsenal.upgrade.get("Semi-Shotgun Cannonade")
    mod4 = arsenal.upgrade.get("Hunter Munitions")
    mod5 = arsenal.upgrade.get("Primed Chilling Grasp")
    mod6 = arsenal.upgrade.get("Primed Ravage")
    mod7 = arsenal.upgrade.get("Critical Deceleration")
    mod8 = arsenal.upgrade.get("Toxic Barrage")
    exilus = arsenal.upgrade.get("Vigilante Supplies")
    arcane = arsenal.upgrade.get("Primary Merciless")
    buff = build_buff()
    build = Build(mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8, exilus, arcane, buff)
    target = arsenal.enemy.get("Exo Gokstad Officer").set(level=235, steel_path=True)
    weapon.configure(build, target)

    print(weapon.format.summary())
    print(weapon.format.upgrades())


if __name__ == "__main__":
    main()