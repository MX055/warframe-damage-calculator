from typing import Any


class WeaponFormatter:
    def __init__(self, weapon: Any) -> None:
        self.weapon = weapon

    def upgrades(self) -> str:
        contributions = self.weapon.stats.contribution_proportions()
        if not contributions: return ""
        max_len = max(len(name) for name in contributions)
        return "\n".join(f"{f'{name}:':<{max_len + 1}} {contribution:.2%}" for name, contribution in contributions.items())
