from warframe_damage_calculator import Calculator, Loadout, Optimizer, arsenal


def test_optimizer_preserves_locked_loadout_and_uses_budget():
    weapon = arsenal.primary.get("Braton Prime")
    locked = arsenal.mod.get("Serration")
    optimizer = Optimizer(Calculator(weapon, loadout=Loadout(mods=[locked])))
    result = optimizer.resolve(metric=lambda calculation: calculation.aggregate.average.total_dps, evaluations=8)
    assert locked in result.loadout.mods
    assert result.evaluations <= 8
    assert result.score >= 0


def test_optimizer_normalizes_attack_and_bodypart_weights():
    weapon = arsenal.primary.get("Braton Prime")
    optimizer = Optimizer(Calculator(weapon))
    result = optimizer.resolve(attack=weapon.default_attack, body_part="body", evaluations=2)
    assert result.evaluations <= 2
    assert result.resolutions >= result.evaluations


def test_optimizer_does_not_select_unimplemented_perks():
    weapon = arsenal.primary.get("Braton")
    optimizer = Optimizer(Calculator(weapon))
    pools = optimizer._candidate_pools()
    assert all(perk.implemented for choices in pools["perks"].values() for perk in choices)


def test_optimizer_uses_terminal_progress_by_default(capsys):
    weapon = arsenal.primary.get("Braton Prime")
    Optimizer(Calculator(weapon)).resolve(evaluations=2)
    output = capsys.readouterr().out
    assert "Optimizing " in output
    assert "Complete " not in output
    assert output.endswith("\r")
    assert "[" not in output


def test_optimizer_can_disable_progress(capsys):
    weapon = arsenal.primary.get("Braton Prime")
    Optimizer(Calculator(weapon)).resolve(evaluations=2, progress=None)
    assert capsys.readouterr().out == ""


def test_optimizer_reports_structured_progress():
    from warframe_damage_calculator import OptimizationProgress

    weapon = arsenal.primary.get("Braton Prime")
    snapshots = []
    optimization = Optimizer(Calculator(weapon)).resolve(evaluations=2, progress=snapshots.append)
    assert snapshots
    assert all(isinstance(snapshot, OptimizationProgress) for snapshot in snapshots)
    assert snapshots[-1].complete
    assert snapshots[-1].stage == "Complete"
    assert snapshots[-1].fraction == 1.0
    assert snapshots[-1].evaluations == optimization.evaluations
    assert snapshots[-1].resolutions == optimization.resolutions
    assert snapshots[-1].best_score == optimization.score
    assert optimization.summary is not None
    assert optimization.summary["evaluation_budget"] == 2
    assert optimization.summary["resolutions"] == optimization.resolutions


def test_optimizer_progress_includes_rebuild_stage():
    from warframe_damage_calculator.engine.optimizer import _ProgressReporter, _ProgressState

    reporter = _ProgressReporter(None, budget=100)
    fraction, stage_fraction = reporter._fractions(_ProgressState(completed=70, stage="Rebuilds", stage_started=60, stage_total=20))
    assert stage_fraction == 0.5
    assert abs(fraction - 0.8) < 1e-12


def test_optimizer_rejects_non_callable_progress():
    weapon = arsenal.primary.get("Braton Prime")
    try:
        Optimizer(Calculator(weapon)).resolve(evaluations=2, progress=True)
    except TypeError as error:
        assert str(error) == "progress must be callable or None"
    else:
        raise AssertionError("Expected TypeError")


def test_optimizer_generates_riven_candidates_when_unlocked():
    weapon = arsenal.primary.get("Vectis Prime")
    optimizer = Optimizer(Calculator(weapon))
    pools = optimizer._candidate_pools()
    assert pools["rivens"]
    assert all(mod.name == "Riven" for mod in pools["rivens"])
    assert len({tuple((stat, tuple(effect.value for effect in effects)) for stat, effects in mod.stats.items()) for mod in pools["rivens"]}) == len(pools["rivens"])
    assert all(mod.slot == "regular_mod" for mod in pools["rivens"])


def test_optimizer_preserves_locked_riven():
    from warframe_damage_calculator import Mod, UpgradeStats

    weapon = arsenal.primary.get("Vectis Prime")
    locked = Mod(name="Riven", stats=UpgradeStats(multishot=1.0))
    optimizer = Optimizer(Calculator(weapon, loadout=Loadout(mods=[locked])))
    assert optimizer._candidate_pools()["rivens"] == ()
    result = optimizer.resolve(evaluations=2, progress=None)
    assert any(mod.name == "Riven" for mod in result.loadout.mods)


def test_optimizer_searches_all_progenitor_elements_when_unlocked():
    from warframe_damage_calculator import Progenitor

    weapon = arsenal.secondary.get("Kuva Nukor")
    optimizer = Optimizer(Calculator(weapon))
    pools = optimizer._candidate_pools()
    assert {progenitor.element for progenitor in pools["progenitors"]} == {"impact", "heat", "cold", "electricity", "toxin", "magnetic", "radiation"}
    loadout = Loadout(progenitor=Progenitor("heat", 0.6))
    neighbors = list(optimizer._exact_neighbors(loadout, pools))
    assert {candidate.progenitor.element for candidate in neighbors if candidate.progenitor is not None} >= {"impact", "cold", "electricity", "toxin", "magnetic", "radiation"}


def test_optimizer_replaces_unlocked_evolutions_during_contextual_search():
    weapon = arsenal.primary.get("Vectis Prime")
    selected = weapon.perk_choices[2][1]
    alternative = weapon.perk_choices[2][2]
    optimizer = Optimizer(Calculator(weapon))
    pools = optimizer._candidate_pools(riven=False)
    neighbors = list(optimizer._exact_neighbors(Loadout(evolutions=[selected]), pools))
    assert any(alternative in candidate.evolutions and selected not in candidate.evolutions for candidate in neighbors)


def test_optimizer_seeds_dot_weakpoint_synergies():
    weapon = arsenal.primary.get("Vectis Prime")
    optimizer = Optimizer(Calculator(weapon))
    pools = optimizer._candidate_pools(search_scale=2.0)
    seeds = optimizer._seed_loadouts(optimizer.calculator.loadout, pools, search_scale=2.0)
    required = {"Primary Acuity", "Rime Rounds", "Malignant Force"}
    assert any(required <= {mod.name for mod in seed.mods} and any(arcane.name == "Primary Merciless" for arcane in seed.arcanes) for seed in seeds)


def test_optimizer_filters_weapon_specific_arcanes_and_beam_exilus_mods():
    weapon = arsenal.primary.get("Vectis Prime")
    pools = Optimizer(Calculator(weapon))._candidate_pools()
    assert "Shotgun Vendetta" not in {arcane.name for arcane in pools["arcanes"]}
    assert "Sinister Reach" not in {mod.name for mod in pools["mods"]}
    assert "Tainted Mag" not in {mod.name for mod in pools["mods"]}
    assert "Primary Overcharge" not in {arcane.name for arcane in pools["arcanes"]}


def test_optimizer_can_disable_riven_search():
    weapon = arsenal.primary.get("Vectis Prime")
    optimizer = Optimizer(Calculator(weapon))
    assert optimizer._candidate_pools(riven=False)["rivens"] == ()
    result = optimizer.resolve(evaluations=2, progress=None, riven=False)
    assert not any(mod.name == "Riven" for mod in result.loadout.mods)


def test_optimizer_validates_riven_flag():
    weapon = arsenal.primary.get("Vectis Prime")
    optimizer = Optimizer(Calculator(weapon))
    try:
        optimizer.resolve(evaluations=2, progress=None, riven=1)
    except TypeError as error:
        assert str(error) == "riven must be a bool"
    else:
        raise AssertionError("Expected TypeError")






def test_optimizer_defaults_to_20000_evaluations():
    import inspect

    assert inspect.signature(Optimizer.resolve).parameters["evaluations"].default == 20_000


def test_optimizer_can_disable_evolution_search():
    weapon = arsenal.primary.get("Phenmor")
    optimizer = Optimizer(Calculator(weapon))
    assert optimizer._candidate_pools(evolutions=False)["perks"] == {}
    result = optimizer.resolve(evaluations=2, progress=None, riven=False, evolutions=False)
    assert not result.loadout.evolutions


def test_optimizer_preserves_locked_evolutions_when_search_is_disabled():
    weapon = arsenal.primary.get("Phenmor")
    locked = arsenal.perk.get("Devouring Attrition")
    optimizer = Optimizer(Calculator(weapon, loadout=Loadout(evolutions=[locked])))
    result = optimizer.resolve(evaluations=2, progress=None, riven=False, evolutions=False)
    assert locked in result.loadout.evolutions


def test_optimizer_validates_evolutions_flag():
    weapon = arsenal.primary.get("Phenmor")
    optimizer = Optimizer(Calculator(weapon))
    try:
        optimizer.resolve(evaluations=2, progress=None, evolutions=1)
    except TypeError as error:
        assert str(error) == "evolutions must be a bool"
    else:
        raise AssertionError("Expected TypeError")


def test_optimizer_scales_with_evaluation_budget():
    weapon = arsenal.primary.get("Braton Prime")
    optimizer = Optimizer(Calculator(weapon))
    result = optimizer.resolve(evaluations=8, progress=None, riven=False)
    assert result.evaluations <= 8
    assert result.summary is not None
    assert "mode" not in result.summary
    assert result.summary["resolution_budget"] == 8
    assert result.summary["budget_exhausted"] == (result.evaluations == 8)


def test_optimizer_candidate_pools_scale_with_evaluation_budget():
    weapon = arsenal.primary.get("Vectis Prime")
    optimizer = Optimizer(Calculator(weapon))
    small = optimizer._candidate_pools(riven=True, search_scale=0.5)
    large = optimizer._candidate_pools(riven=True, search_scale=2.0)
    assert len(large["mods"]) >= len(small["mods"])
    assert len(large["arcanes"]) >= len(small["arcanes"])
    assert len(large["rivens"]) >= len(small["rivens"])


def test_optimizer_blacklists_external_condition_upgrades_and_faction_mods():
    weapon = arsenal.primary.get("Vectis Prime")
    pools = Optimizer(Calculator(weapon))._candidate_pools(riven=False)
    names = {upgrade.name for upgrade in (*pools["mods"], *pools["arcanes"])}
    assert "Spectral Serration" not in names
    assert "Primary Overcharge" not in names
    assert "Bane of Grineer" not in names
    assert "Primed Bane of Grineer" not in names
    assert "Serration" in names


def test_optimizer_user_upgrade_blacklist_replaces_defaults():
    weapon = arsenal.primary.get("Vectis Prime")
    pools = Optimizer(Calculator(weapon))._candidate_pools(riven=False, upgrade_blacklist={"Serration"}, search_scale=4.0)
    names = {upgrade.name for upgrade in (*pools["mods"], *pools["arcanes"])}
    assert "Serration" not in names
    assert "Spectral Serration" in names
    assert "Primed Bane of Grineer" in names


def test_optimizer_none_upgrade_blacklist_disables_defaults():
    weapon = arsenal.primary.get("Vectis Prime")
    pools = Optimizer(Calculator(weapon))._candidate_pools(riven=False, upgrade_blacklist=None, search_scale=4.0)
    names = {upgrade.name for upgrade in (*pools["mods"], *pools["arcanes"])}
    assert "Spectral Serration" in names
    assert "Primed Bane of Grineer" in names


def test_optimizer_blacklists_faction_riven_stats():
    weapon = arsenal.primary.get("Vectis Prime")
    rivens = Optimizer(Calculator(weapon))._candidate_pools()["rivens"]
    assert rivens
    assert all(not {"corpus_damage", "corrupted_damage", "grineer_damage", "infested_damage"}.intersection(riven.stats) for riven in rivens)


def test_optimizer_user_riven_stat_blacklist_replaces_defaults(monkeypatch):
    weapon = arsenal.primary.get("Vectis Prime")
    optimizer = Optimizer(Calculator(weapon))
    captured = None

    def capture(*, limit, stat_blacklist):
        nonlocal captured
        captured = frozenset(stat_blacklist)
        return ()

    monkeypatch.setattr(Optimizer, "_riven_candidates", lambda self, *, limit, stat_blacklist: capture(limit=limit, stat_blacklist=stat_blacklist))
    optimizer._candidate_pools(riven_stat_blacklist={"crit_chance"})
    assert captured == frozenset({"crit_chance"})


def test_optimizer_none_riven_stat_blacklist_disables_defaults(monkeypatch):
    weapon = arsenal.primary.get("Vectis Prime")
    optimizer = Optimizer(Calculator(weapon))
    captured = None

    def capture(*, limit, stat_blacklist):
        nonlocal captured
        captured = frozenset(stat_blacklist)
        return ()

    monkeypatch.setattr(Optimizer, "_riven_candidates", lambda self, *, limit, stat_blacklist: capture(limit=limit, stat_blacklist=stat_blacklist))
    optimizer._candidate_pools(riven_stat_blacklist=None)
    assert captured == frozenset()


def test_optimizer_progress_argument_is_last():
    import inspect

    assert next(reversed(inspect.signature(Optimizer.resolve).parameters)) == "progress"


def test_optimizer_blacklists_are_signature_defaults():
    import inspect
    from warframe_damage_calculator.engine.optimizer import DEFAULT_RIVEN_STAT_BLACKLIST, DEFAULT_UPGRADE_BLACKLIST

    parameters = inspect.signature(Optimizer.resolve).parameters
    assert parameters["upgrade_blacklist"].default == DEFAULT_UPGRADE_BLACKLIST
    assert parameters["riven_stat_blacklist"].default == DEFAULT_RIVEN_STAT_BLACKLIST
