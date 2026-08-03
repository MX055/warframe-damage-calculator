from warframe_damage_calculator import Calculator, Build, Optimizer, State, arsenal


def test_optimizer_preserves_locked_build_and_uses_budget():
    weapon = arsenal.primary.get("Braton Prime")
    locked = arsenal.mod.get("Serration")
    optimizer = Optimizer(Calculator(weapon, build=Build(mods=[locked])))
    result = optimizer.resolve(metric=lambda calculation: calculation.aggregate.damage.total_dps, evaluations=8)
    assert locked in result.build.mods
    assert result.evaluations <= 8
    assert result.score >= 0


def test_optimizer_normalizes_attack_and_body_part_weights():
    weapon = arsenal.primary.get("Braton Prime")
    optimizer = Optimizer(Calculator(weapon))
    result = optimizer.resolve(attack=weapon.default_attack, body_part="body", evaluations=2)
    assert result.evaluations <= 2
    assert result.resolutions >= result.evaluations


def test_optimizer_rebuilds_upgrade_generated_attack_trees():
    weapon = arsenal.primary.get("Kuva Ogris")
    napalm = arsenal.mod.get("Nightwatch Napalm")
    optimizer = Optimizer(Calculator(weapon, build=Build(mods=[napalm])))
    result = optimizer.resolve(attack="rocket_impact", evaluations=2, riven=False, evolutions=False, upgrade_blacklist=set(arsenal.mod) | set(arsenal.arcane), progress=None)
    assert "nightwatch_napalm_linger" in result.result.attacks
    generated = optimizer.resolve(attack="nightwatch_napalm_linger", evaluations=2, riven=False, evolutions=False, upgrade_blacklist=set(arsenal.mod) | set(arsenal.arcane), progress=None)
    assert list(generated.result.attacks) == ["nightwatch_napalm_linger"]


def test_parallel_optimizer_supports_status_generated_attacks():
    weapon = arsenal.melee.get("Xoris")
    influence = arsenal.arcane.get("Melee Influence")
    optimizer = Optimizer(Calculator(weapon, build=Build(mods=[arsenal.mod.get("Shocking Touch")], arcanes=[influence])))
    result = optimizer.resolve(evaluations=2, workers=2, riven=False, evolutions=False, upgrade_blacklist=set(arsenal.mod) | set(arsenal.arcane), progress=None)
    assert "melee_influence" in result.result.attacks


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


def test_parallel_optimizer_preserves_search_results():
    calculator = Calculator(arsenal.primary.get("Kuva Ogris"))
    sequential = Optimizer(calculator).resolve(evaluations=64, workers=1, progress=None)
    parallel = Optimizer(calculator).resolve(evaluations=64, workers=2, progress=None)
    assert parallel.evaluations == sequential.evaluations
    assert parallel.score == sequential.score
    assert [mod.name for mod in parallel.build.mods] == [mod.name for mod in sequential.build.mods]
    assert [arcane.name for arcane in parallel.build.arcanes] == [arcane.name for arcane in sequential.build.arcanes]
    assert parallel.build.evolutions == sequential.build.evolutions
    assert parallel.build.progenitor == sequential.build.progenitor


def test_optimizer_propagates_state_to_parallel_scoring_and_results():
    calculator = Calculator(arsenal.melee.get("Xoris"))
    sequential = Optimizer(calculator).resolve(attack="heavy_slam_attack", state=State(combo_multiplier=12), evaluations=16, workers=1, progress=None)
    parallel = Optimizer(calculator).resolve(attack="heavy_slam_attack", state={"combo_multiplier": 12}, evaluations=16, workers=2, progress=None)
    default_state = Optimizer(calculator).resolve(attack="heavy_slam_attack", evaluations=16, workers=1, progress=None)
    assert parallel.score == sequential.score
    assert parallel.result.state == {"combo_multiplier": 12}
    assert parallel.score != default_state.score


def test_optimizer_rejects_unknown_state_fields():
    optimizer = Optimizer(Calculator(arsenal.primary.get("Braton Prime")))
    try:
        optimizer.resolve(state={"unknown": True}, evaluations=1, progress=None)
    except TypeError as error:
        assert str(error) == "unknown calculation state fields: unknown"
    else:
        raise AssertionError("Expected TypeError")


def test_compact_optimizer_score_matches_full_result():
    from warframe_damage_calculator.optimizer import balanced_damage_metric

    optimizer = Optimizer(Calculator(arsenal.primary.get("Kuva Ogris"), build=Build(mods=[arsenal.mod.get("Nightwatch Napalm")])))
    result = optimizer.resolve(attack="rocket_impact", evaluations=8, workers=1, progress=None)
    assert result.score == balanced_damage_metric(result.result)


def _half_aoe_compact(direct_dph, dot_dph, direct_dps, dot_dps, damage_mass):
    from warframe_damage_calculator.engine.metrics import balanced_damage_components

    mass = 1.0 + 0.5 * (damage_mass - 1.0)
    return balanced_damage_components(direct_dph, dot_dph, direct_dps, dot_dps, mass)


def test_custom_compact_metric_uses_parallel_workers():
    from concurrent import futures

    calculator = Calculator(arsenal.primary.get("Kuva Ogris"))
    sequential = Optimizer(calculator).resolve(compact_metric=_half_aoe_compact, evaluations=64, workers=1, progress=None)
    parallel = Optimizer(calculator).resolve(compact_metric=_half_aoe_compact, evaluations=64, workers=2, progress=None)
    full_metric = Optimizer(calculator).resolve(metric=lambda result: result.aggregate.damage.total_dps, evaluations=8, workers=2, progress=None)
    assert parallel.evaluations == sequential.evaluations
    assert parallel.score == sequential.score
    assert [mod.name for mod in parallel.build.mods] == [mod.name for mod in sequential.build.mods]
    if getattr(futures, "InterpreterPoolExecutor", None) is not None:
        assert parallel.workers == 2
        assert full_metric.workers == 1


def test_optimizer_rejects_non_callable_compact_metric():
    optimizer = Optimizer(Calculator(arsenal.primary.get("Braton Prime")))
    try:
        optimizer.resolve(compact_metric="balanced", evaluations=1, progress=None)
    except TypeError as error:
        assert str(error) == "compact_metric must be callable or None"
    else:
        raise AssertionError("Expected TypeError")


def test_balanced_damage_metric_includes_generated_attack_spatial_mass():
    from warframe_damage_calculator.optimizer import balanced_damage_metric

    weapon = arsenal.melee.get("Xoris")
    electricity = arsenal.mod.get("Shocking Touch")
    without = Calculator(weapon, build=Build(mods=[electricity])).resolve()
    with_influence = Calculator(weapon, build=Build(mods=[electricity], arcanes=[arsenal.arcane.get("Melee Influence")])).resolve()
    assert "melee_influence" in with_influence.attacks
    assert with_influence.weapon.attacks["melee_influence"].hits_source is False
    assert with_influence.aggregate.damage.total_dph == without.aggregate.damage.total_dph
    assert balanced_damage_metric(with_influence) > balanced_damage_metric(without)


def test_optimizer_seeds_generated_attack_status_dependencies():
    optimizer = Optimizer(Calculator(arsenal.melee.get("Xoris")))
    pools = optimizer._candidate_pools(riven=False)
    influence_seeds = [seed for seed in optimizer._seed_builds(optimizer.calculator.build, pools) if any(arcane.name == "Melee Influence" for arcane in seed.arcanes)]
    assert influence_seeds
    assert any("electricity" in mod.stats for seed in influence_seeds for mod in seed.mods)
    assert any(not ({stat for mod in seed.mods for stat in mod.stats} & {"heat", "cold", "toxin"}) for seed in influence_seeds)


def test_optimizer_validates_workers():
    optimizer = Optimizer(Calculator(arsenal.primary.get("Braton Prime")))
    for workers in (0, -1, True, 1.5):
        try:
            optimizer.resolve(evaluations=1, workers=workers, progress=None)
        except ValueError as error:
            assert str(error) == "workers must be a positive integer or None"
        else:
            raise AssertionError("Expected ValueError")


def test_optimizer_reports_structured_progress():
    from warframe_damage_calculator.optimizer.progress import OptimizationProgress

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
    assert optimization.evaluation_budget == 2
    assert optimization.resolutions == optimization.resolutions


def test_optimizer_progress_includes_rebuild_stage():
    from warframe_damage_calculator.optimizer.progress import _ProgressReporter, _ProgressState

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
    from warframe_damage_calculator.domain.upgrades import Mod, UpgradeStats

    weapon = arsenal.primary.get("Vectis Prime")
    locked = Mod(name="Riven", stats=UpgradeStats(multishot=1.0))
    optimizer = Optimizer(Calculator(weapon, build=Build(mods=[locked])))
    assert optimizer._candidate_pools()["rivens"] == ()
    result = optimizer.resolve(evaluations=2, progress=None)
    assert any(mod.name == "Riven" for mod in result.build.mods)


def test_optimizer_searches_all_progenitor_elements_when_unlocked():
    from warframe_damage_calculator import Progenitor

    weapon = arsenal.secondary.get("Kuva Nukor")
    optimizer = Optimizer(Calculator(weapon))
    pools = optimizer._candidate_pools()
    assert {progenitor.element for progenitor in pools["progenitors"]} == {"impact", "heat", "cold", "electricity", "toxin", "magnetic", "radiation"}
    build = Build(progenitor=Progenitor(element="heat", bonus=0.6))
    neighbors = list(optimizer._exact_neighbors(build, pools))
    assert {candidate.progenitor.element for candidate in neighbors if candidate.progenitor is not None} >= {"impact", "cold", "electricity", "toxin", "magnetic", "radiation"}


def test_optimizer_replaces_unlocked_evolutions_during_contextual_search():
    weapon = arsenal.primary.get("Vectis Prime")
    selected = weapon.perk_choices[2][1]
    alternative = weapon.perk_choices[2][2]
    optimizer = Optimizer(Calculator(weapon))
    pools = optimizer._candidate_pools(riven=False)
    neighbors = list(optimizer._exact_neighbors(Build(evolutions=[selected]), pools))
    assert any(alternative in candidate.evolutions and selected not in candidate.evolutions for candidate in neighbors)


def test_optimizer_seeds_dot_weak_point_synergies():
    weapon = arsenal.primary.get("Vectis Prime")
    optimizer = Optimizer(Calculator(weapon))
    pools = optimizer._candidate_pools(search_scale=2.0)
    seeds = optimizer._seed_builds(optimizer.calculator.build, pools, search_scale=2.0)
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
    assert not any(mod.name == "Riven" for mod in result.build.mods)


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
    assert not result.build.evolutions


def test_optimizer_preserves_locked_evolutions_when_search_is_disabled():
    weapon = arsenal.primary.get("Phenmor")
    locked = arsenal.perk.get("Devouring Attrition")
    optimizer = Optimizer(Calculator(weapon, build=Build(evolutions=[locked])))
    result = optimizer.resolve(evaluations=2, progress=None, riven=False, evolutions=False)
    assert locked in result.build.evolutions


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
    assert result.resolution_budget == 8
    assert result.budget_exhausted == (result.evaluations == 8)


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
    assert "Catalyzer Link" in names
    assert "Primed Bane of Grineer" in names


def test_optimizer_none_upgrade_blacklist_disables_defaults():
    weapon = arsenal.primary.get("Vectis Prime")
    pools = Optimizer(Calculator(weapon))._candidate_pools(riven=False, upgrade_blacklist=None, search_scale=4.0)
    names = {upgrade.name for upgrade in (*pools["mods"], *pools["arcanes"])}
    assert "Catalyzer Link" in names
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
    from warframe_damage_calculator.optimizer.candidates import DEFAULT_UPGRADE_BLACKLIST
    from warframe_damage_calculator.optimizer.rivens import DEFAULT_RIVEN_STAT_BLACKLIST

    parameters = inspect.signature(Optimizer.resolve).parameters
    assert parameters["upgrade_blacklist"].default == DEFAULT_UPGRADE_BLACKLIST
    assert parameters["riven_stat_blacklist"].default == DEFAULT_RIVEN_STAT_BLACKLIST
