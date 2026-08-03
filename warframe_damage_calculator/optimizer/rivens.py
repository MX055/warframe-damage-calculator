from collections.abc import Collection

from ..database.arsenal import arsenal
from ..domain.upgrades import Mod, UpgradeStats


RIVEN_ROLLS = ((2, 0, 0.99, 0.0), (2, 1, 1.2375, -0.495), (3, 0, 0.75, 0.0), (3, 1, 0.9375, -0.75))
RIVEN_NON_NEGATIVE = frozenset({"cold", "electricity", "heat", "punch_through", "toxin"})
RIVEN_RELEVANT = frozenset({"damage_bonus", "cold", "crit_chance", "crit_damage", "corpus_damage", "electricity", "fire_rate", "grineer_damage", "heat", "impact", "infested_damage", "magazine_capacity", "multishot", "punch_through", "puncture", "reload_speed", "slash", "slide_crit_chance", "status_chance", "status_duration", "toxin"})
FACTION_DAMAGE_STATS = frozenset({"corpus_damage", "corrupted_damage", "grineer_damage", "infested_damage"})
DEFAULT_RIVEN_STAT_BLACKLIST = FACTION_DAMAGE_STATS


class RivenCandidates:
    def _riven_candidates(self, *, limit: int = 32, stat_blacklist: Collection[str] = ()) -> tuple[Mod, ...]:
        category = self._riven_category()
        if category is None or self.calculator.weapon.disposition <= 0: return ()
        base_stats = arsenal.database.get("riven_stats", {}).get(category, {})
        if not base_stats: return ()
        positive_stats = [stat for stat in base_stats if stat in RIVEN_RELEVANT and stat not in stat_blacklist]
        positive_stats.sort(key=lambda stat: self._riven_stat_priority(stat, float(base_stats[stat])), reverse=True)
        positive_stats = positive_stats[:14 if limit > 32 else 10]
        negative_stats = [stat for stat in base_stats if stat not in RIVEN_NON_NEGATIVE and stat not in stat_blacklist]
        negative_stats.sort(key=lambda stat: self._riven_negative_priority(stat, float(base_stats[stat])))
        negative_stats = negative_stats[:10 if limit > 32 else 6]
        candidates: dict[tuple[tuple[str, float], ...], Mod] = {}
        disposition = float(self.calculator.weapon.disposition)
        from itertools import combinations
        for positive_count, negative_count, positive_factor, negative_factor in RIVEN_ROLLS:
            for positives in combinations(positive_stats, positive_count):
                negatives = (None,) if negative_count == 0 else tuple(stat for stat in negative_stats if stat not in positives)
                for negative in negatives:
                    fields = {stat: float(base_stats[stat]) * disposition * positive_factor * 1.1 for stat in positives}
                    if negative is not None: fields[negative] = float(base_stats[negative]) * disposition * negative_factor * 0.9
                    key = tuple(sorted(fields.items()))
                    candidates[key] = Mod(name="Riven", stats=UpgradeStats(**fields))
        ranked = sorted(candidates.values(), key=self._upgrade_priority, reverse=True)
        return tuple(ranked[:limit])

    def _riven_category(self) -> str | None:
        weapon = self.calculator.weapon
        if weapon.type == "melee": return "melee"
        if weapon.type == "secondary": return "pistol"
        if weapon.type == "archgun": return "archgun"
        if weapon.type == "primary": return "shotgun" if weapon.subtype == "shotgun" else "rifle"
        return None

    def _riven_stat_priority(self, stat: str, value: float) -> tuple[float, float, str]:
        mod = Mod(name=f"Riven {stat}", stats=UpgradeStats(**{stat: value * max(float(self.calculator.weapon.disposition), 0.0)}))
        priority, _, _ = self._upgrade_priority(mod)
        preferred = 1.0 if stat in {"damage_bonus", "multishot", "crit_chance", "crit_damage", "slide_crit_chance", "status_chance", "fire_rate", "reload_speed", "cold", "electricity", "heat", "toxin"} else 0.0
        return preferred, priority, stat

    def _riven_negative_priority(self, stat: str, value: float) -> tuple[int, float, str]:
        harmless = stat in {"ammo_maximum", "projectile_speed", "recoil", "zoom"}
        return (0 if harmless else 1), abs(value), stat

    def _is_riven(self, mod: Mod) -> bool:
        return mod.name.casefold() == "riven"

    def _riven_signature(self, mod: Mod) -> tuple[tuple[str, tuple[object, ...]], ...]:
        return tuple((stat, tuple(effect.value for effect in effects)) for stat, effects in mod.stats.items())


