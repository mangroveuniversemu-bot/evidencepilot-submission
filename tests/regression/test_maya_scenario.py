"""The hero scenario, frozen.

If any number here moves, the demo changed. That is either a bug or a
deliberate edit to `examples/maya_case`, and it should never happen silently.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(scope="module")
def expected(repo_root):
    return json.loads(
        (repo_root / "examples" / "maya_case" / "expected" / "verdict.json").read_text()
    )


def test_verdict_fields_are_unchanged(maya_run, expected):
    card = maya_run.card
    assert card.claim_id == expected["claim_id"]
    assert card.verdict.value == expected["verdict"]
    assert card.claim_state.value == expected["claim_state"]
    assert card.evidence_class.value == expected["evidence_class"]
    assert card.fired_rule == expected["fired_rule"]


def test_numbers_are_unchanged(maya_run, expected):
    for key, value in expected["numbers"].items():
        assert maya_run.card.numbers[key] == pytest.approx(value, abs=1e-6), key


def test_the_replay_does_not_violate_the_classical_bound(maya_run):
    result = maya_run.assessment.replay.registered
    assert result.s_value == pytest.approx(1.9625, abs=1e-9)
    assert not result.violates_bound
    assert result.sigma_above_bound < -3.0


def test_the_claimed_value_is_reproduced_only_by_the_wrong_convention(maya_run):
    root = maya_run.assessment.root_cause
    assert root.full_matches == ("no_channel_correction:BLK-02",)
    candidate = next(
        c for c in root.candidates if c.deviation.deviation_id == "no_channel_correction:BLK-02"
    )
    # 2.6125 rounds to the 2.61 that was submitted.
    assert candidate.s_value == pytest.approx(2.6125, abs=1e-9)


def test_the_difference_is_systematic_not_statistical(maya_run):
    replay = maya_run.assessment.replay
    assert abs(replay.delta_in_sigma) > 50
    detail = maya_run.card.findings[-1].detail
    assert "systematic, not statistical" in detail


def test_escalation_matches_the_frozen_options(maya_run, expected):
    escalation = maya_run.card.escalation
    assert escalation is not None
    assert escalation.recommended_option_id == expected["escalation"]["recommended_option_id"]
    assert [o.option_id for o in escalation.options] == expected["escalation"]["option_ids"]
