"""Every verdict rule must be reachable from a real package, not just a unit test.

A rule exercised only by an in-memory assessment is a rule nobody has watched
run end to end. This file is the check that the fixture set keeps up with the
rule table: add a rule without a package that fires it and the build goes red.
"""

from __future__ import annotations

import pathlib

import pytest

from agent.researchops_agent import verify_package
from agent.schemas import ClaimState, EvidenceClass, Verdict
from policy.verdict_rules import RULES

#: Package -> (rule, verdict, claim state) it is expected to land on.
COVERAGE = {
    "examples/adversarial/case_j_incomplete_counts/inputs": (
        "R-001",
        Verdict.BLOCK,
        ClaimState.UNVERIFIED,
    ),
    "examples/adversarial/case_a_stale_artifact/inputs": (
        "R-002",
        Verdict.BLOCK,
        ClaimState.UNVERIFIED,
    ),
    "examples/adversarial/case_h_unphysical_claim/inputs": (
        "R-005",
        Verdict.BLOCK,
        ClaimState.NOT_REPRODUCED,
    ),
    "examples/adversarial/case_i_unphysical_convention/inputs": (
        "R-004",
        Verdict.BLOCK,
        ClaimState.UNVERIFIED,
    ),
    "examples/maya_case/inputs": ("R-005", Verdict.BLOCK, ClaimState.NOT_REPRODUCED),
    "examples/adversarial/case_d_human_decision/inputs": (
        "R-006",
        Verdict.HUMAN_DECISION,
        ClaimState.INCONCLUSIVE,
    ),
    "examples/adversarial/case_c_missing_evidence/inputs": (
        "R-007",
        Verdict.REVIEW,
        ClaimState.REPRODUCED,
    ),
    "examples/adversarial/case_k_missing_environment/inputs": (
        "R-008",
        Verdict.REVIEW,
        ClaimState.REPRODUCED,
    ),
    "examples/adversarial/case_e_clean_pass/inputs": (
        "R-009",
        Verdict.ALLOW,
        ClaimState.REPRODUCED,
    ),
    "examples/adversarial/case_l_finite_sample_boundary/inputs": (
        "R-010",
        Verdict.REVIEW,
        ClaimState.REPRODUCED,
    ),
    "examples/adversarial/case_m_algebraic_claim/inputs": (
        "R-003",
        Verdict.BLOCK,
        ClaimState.NOT_REPRODUCED,
    ),
}


def _all_fixtures(repo_root) -> list[pathlib.Path]:
    return [repo_root / "examples" / "maya_case" / "inputs"] + sorted(
        (repo_root / "examples" / "adversarial").glob("*/inputs")
    )


def test_generated_examples_match_repository_without_overwriting_it(
    repo_root, tmp_path, monkeypatch
):
    from scripts import build_examples

    monkeypatch.setattr(build_examples, "EXAMPLES", tmp_path)
    assert build_examples.main() == 0
    generated = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert len(list(tmp_path.rglob("manifest.json"))) == 12
    for path in generated:
        relative = path.relative_to(tmp_path)
        expected = repo_root / "examples" / relative
        assert expected.is_file(), f"missing generated fixture: {relative}"
        assert path.read_bytes() == expected.read_bytes(), f"fixture drift: {relative}"


def test_every_rule_fires_from_some_package(repo_root):
    fired = {verify_package(path).card.fired_rule for path in _all_fixtures(repo_root)}
    declared = {rule.rule_id for rule in RULES}
    missing = sorted(declared - fired)
    assert not missing, f"rules with no package that reaches them: {missing}"


def test_the_fallback_stays_unreachable(repo_root):
    """R-000 exists so an unforeseen combination escalates rather than passing.

    If a package ever reaches it, the rule table has a hole.
    """
    fired = {verify_package(path).card.fired_rule for path in _all_fixtures(repo_root)}
    assert "R-000" not in fired


@pytest.mark.parametrize("relative,expected", COVERAGE.items())
def test_each_package_lands_on_its_rule(repo_root, relative, expected):
    card = verify_package(repo_root / relative).card
    assert (card.fired_rule, card.verdict, card.claim_state) == expected


def test_missing_acquisition_block_is_reported_not_averaged_over(repo_root):
    """R-001: three setting pairs cannot be combined into a four-term statistic."""
    run = verify_package(repo_root / "examples/adversarial/case_j_incomplete_counts/inputs")
    assert run.assessment.replay is None
    assert "ap_bp" in run.assessment.replay_error
    assert run.card.evidence_class is EvidenceClass.NONE


def test_historical_unphysical_fixture_is_a_reproduction_failure(repo_root):
    """Reject the actual numerical mismatch, not the mere crossing of a bound."""
    run = verify_package(repo_root / "examples/adversarial/case_h_unphysical_claim/inputs")
    assert run.card.fired_rule == "R-005"
    assert not run.assessment.replay.agrees
    assert "impossible" not in run.card.model_dump_json().lower()
    claim = run.assessment.package.claim
    assert all(abs(e) <= 1.0 for e in claim.per_pair_correlation.values())
    assert claim.value > run.assessment.replay.registered.tsirelson_bound


def test_a_broken_convention_is_blamed_on_the_convention(repo_root):
    """R-004: reject the unsupported all-positive expression, not sample magnitude."""
    run = verify_package(repo_root / "examples/adversarial/case_i_unphysical_convention/inputs")
    result = run.assessment.replay.registered
    assert not run.assessment.replay.diagnostics.convention_valid
    assert abs(run.assessment.package.claim.value) <= result.tsirelson_bound
    assert "convention file" in run.card.findings[-1].detail


def test_registered_but_incomplete_is_review_not_block(repo_root):
    """R-008: the convention is registered and the numbers agree; the record does not."""
    run = verify_package(repo_root / "examples/adversarial/case_k_missing_environment/inputs")
    assert run.assessment.package.convention.is_registered
    assert run.assessment.replay.agrees
    assert not run.assessment.provenance.complete
    assert run.card.escalation is not None
