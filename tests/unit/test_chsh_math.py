"""The arithmetic the entire product rests on."""

from __future__ import annotations

import math

import pytest

from agent.schemas import BlockConvention, Convention, CountRow
from tools.chsh_replay import ReplayError, compute_chsh, correct_counts, correlation


def test_correlation_matches_definition():
    e_value, sigma, total = correlation(8850, 1194, 1181, 8775)
    assert total == 20000
    assert e_value == pytest.approx(0.7625, abs=1e-12)
    # Var(E) = (1 - E^2) / N for a sample mean of a +/-1 variable.
    assert sigma == pytest.approx(math.sqrt((1 - 0.7625**2) / 20000), rel=1e-12)


def test_correlation_bounds():
    assert correlation(100, 0, 0, 0)[0] == 1.0
    assert correlation(0, 100, 0, 0)[0] == -1.0
    assert correlation(50, 50, 0, 0)[0] == 0.0
    # A perfectly correlated sample has zero sample variance.
    assert correlation(100, 0, 0, 0)[1] == 0.0


def test_correlation_rejects_empty_pair():
    with pytest.raises(ReplayError):
        correlation(0, 0, 0, 0)


def _row(**kwargs) -> CountRow:
    base = dict(
        block_id="BLK-01",
        subrun_id="S1",
        setting_a="a",
        setting_b="b",
        n_pp=10,
        n_pm=20,
        n_mp=30,
        n_mm=40,
        window_ns=3.0,
    )
    base.update(kwargs)
    return CountRow(**base)


def _convention(**block_kwargs) -> Convention:
    return Convention(
        convention_id="test",
        chsh_combination={"a_b": 1},
        blocks={"BLK-01": BlockConvention(pair="a_b", **block_kwargs)},
    )


def test_bob_inversion_is_an_involution():
    row = _row()
    once = correct_counts(row, _convention(bob_channel_map="inverted"))
    twice = correct_counts(
        row.model_copy(update=dict(zip(("n_pp", "n_pm", "n_mp", "n_mm"), once, strict=True))),
        _convention(bob_channel_map="inverted"),
    )
    assert twice == (row.n_pp, row.n_pm, row.n_mp, row.n_mm)


def test_bob_inversion_flips_the_sign_of_e():
    row = _row(n_pp=8000, n_pm=2000, n_mp=2000, n_mm=8000)
    plain = correlation(*correct_counts(row, _convention()))[0]
    flipped = correlation(*correct_counts(row, _convention(bob_channel_map="inverted")))[0]
    assert flipped == pytest.approx(-plain)


def test_alice_inversion_flips_the_sign_of_e():
    row = _row(n_pp=8000, n_pm=2000, n_mp=2000, n_mm=8000)
    plain = correlation(*correct_counts(row, _convention()))[0]
    flipped = correlation(*correct_counts(row, _convention(alice_channel_map="inverted")))[0]
    assert flipped == pytest.approx(-plain)


def test_unknown_channel_map_is_rejected():
    with pytest.raises(ReplayError, match="bob_channel_map"):
        correct_counts(_row(), _convention(bob_channel_map="sideways"))


def test_block_missing_from_convention_is_rejected():
    convention = Convention(
        convention_id="test",
        chsh_combination={"a_b": 1},
        blocks={"BLK-99": BlockConvention(pair="a_b")},
    )
    with pytest.raises(ReplayError, match="no entry in the registered convention"):
        compute_chsh([_row()], convention)


def test_missing_setting_pair_is_rejected():
    convention = Convention(
        convention_id="test",
        chsh_combination={"a_b": 1, "a_bp": -1},
        blocks={"BLK-01": BlockConvention(pair="a_b")},
    )
    with pytest.raises(ReplayError, match="no surviving data"):
        compute_chsh([_row()], convention)


def test_signs_come_from_the_convention_not_the_code(maya_inputs):
    from tools.artifact_reader import read_package

    package = read_package(maya_inputs)
    registered = compute_chsh(package.counts, package.convention)
    flipped = package.convention.model_copy(
        update={"chsh_combination": {**package.convention.chsh_combination, "a_b": -1}}
    )
    assert compute_chsh(package.counts, flipped).s_value != registered.s_value


def test_empirical_tsirelson_diagnostic_does_not_label_physicality(maya_inputs):
    from tools.artifact_reader import read_package
    from tools.chsh_diagnostics import diagnose_chsh

    package = read_package(maya_inputs)
    result = compute_chsh(package.counts, package.convention)
    assert not diagnose_chsh(package, result).empirical_above_tsirelson
    extreme_sample = result.model_copy(update={"s_value": 3.5})
    assert diagnose_chsh(package, extreme_sample).empirical_above_tsirelson
    assert not hasattr(result, "is_physical")


def test_violation_requires_three_sigma(maya_inputs):
    from tools.artifact_reader import read_package

    package = read_package(maya_inputs)
    result = compute_chsh(package.counts, package.convention)
    assert result.s_value < result.classical_bound
    assert not result.violates_bound
    borderline = result.model_copy(update={"s_value": 2.0 + 2.0 * result.sigma_s})
    assert not borderline.violates_bound
