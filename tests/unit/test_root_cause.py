"""Naming the mistake, not just reporting a difference."""

from __future__ import annotations

import pytest

from tools.artifact_reader import read_package
from tools.root_cause import _tolerance, enumerate_deviations, find_root_cause


def test_tolerance_follows_reported_precision():
    assert _tolerance(2.61) == pytest.approx(0.005)
    assert _tolerance(2.3500) == pytest.approx(0.005)
    assert _tolerance(0.7625) == pytest.approx(0.0005)  # floored, not 5e-5


def test_deviation_space_is_declared_and_finite(maya_inputs):
    package = read_package(maya_inputs)
    deviations = enumerate_deviations(package.counts, package.convention)
    ids = [d.deviation_id for d in deviations]
    assert len(ids) == len(set(ids))
    assert "no_channel_correction:BLK-02" in ids
    assert all(
        d.family in {"measurement_convention", "combination_formula", "post_selection"}
        for d in deviations
    )
    # Only BLK-02 has a non-standard map, so no redundant "ALL" candidate.
    assert "no_channel_correction:ALL" not in ids


def test_two_deviations_reach_the_claimed_value_but_only_one_explains_it(maya_inputs):
    package = read_package(maya_inputs)
    report = find_root_cause(package.counts, package.convention, package.claim)

    # Dropping the BLK-02 channel correction and flipping the a_bp combination
    # sign both land on S = 2.6125.
    assert set(report.value_matches) == {"no_channel_correction:BLK-02", "flip_term_sign:a_bp"}
    # Only one of them also reproduces the reported per-pair correlations.
    assert report.full_matches == ("no_channel_correction:BLK-02",)
    assert report.identified is not None
    assert report.identified.target == "BLK-02"


def test_reported_per_pair_correlations_are_what_disambiguate(maya_inputs):
    package = read_package(maya_inputs)
    blinded = package.claim.model_copy(update={"per_pair_correlation": {}})
    report = find_root_cause(package.counts, package.convention, blinded)
    # Without per-pair numbers the root cause is genuinely ambiguous, and the
    # agent says so instead of picking one.
    assert len(report.full_matches) == 2
    assert report.identified is None
    assert "ambiguous" in report.conclusion


def test_no_explanation_is_reported_honestly(maya_inputs):
    package = read_package(maya_inputs)
    impossible = package.claim.model_copy(update={"value": 1.234, "per_pair_correlation": {}})
    report = find_root_cause(package.counts, package.convention, impossible)
    assert report.full_matches == ()
    assert report.identified is None
    assert "No single known deviation" in report.conclusion
