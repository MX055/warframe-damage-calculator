from ..protocols import WeaponFormatterOwner


class WeaponFormatter:
    def __init__(self, weapon: WeaponFormatterOwner) -> None:
        self.weapon = weapon

    def upgrades(self) -> str:
        contributions = self.weapon.results.contribution_fractions()
        if not contributions: return ""
        max_len = max(len(name) for name in contributions)
        return "\n".join(f"{f'{name}:':<{max_len + 1}} {contribution:.2%}" for name, contribution in contributions.items())
