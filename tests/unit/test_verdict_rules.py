"""Rule ordering is the policy, so it gets tested directly."""

from __future__ import annotations

from agent.schemas import ClaimState, Severity, Verdict
from agent.state import Assessment
from policy.verdict_rules import RULES, apply_rules
from tools.artifact_reader import read_package
from tools.provenance_checker import check_provenance


def _assessment(path) -> Assessment:
    package = read_package(path)
    return Assessment(package=package, provenance=check_provenance(package))


def test_rule_ids_are_unique_and_ordered():
    ids = [rule.rule_id for rule in RULES]
    assert ids == [
        "R-001",
        "R-002",
        "R-004",
        "R-003",
        "R-005",
        "R-006",
        "R-007",
        "R-008",
        "R-010",
        "R-009",
    ]
    assert len(ids) == len(set(ids))


def test_unreplayable_package_outranks_everything(adversarial):
    assessment = _assessment(adversarial / "case_a_stale_artifact" / "inputs")
    assessment = assessment.model_copy(update={"replay_error": "detector table unreadable"})
    outcome = apply_rules(assessment)
    assert outcome.rule_id == "R-001"
    assert outcome.verdict is Verdict.BLOCK


def test_integrity_failure_blocks_before_any_replay(adversarial):
    outcome = apply_rules(_assessment(adversarial / "case_a_stale_artifact" / "inputs"))
    assert outcome.rule_id == "R-002"
    assert outcome.verdict is Verdict.BLOCK
    assert outcome.claim_state is ClaimState.UNVERIFIED


def test_claim_outside_algebraic_range_is_blocked(maya_inputs):
    from agent.researchops_agent import _build_replay_report
    from evidence.execution_trace import Tracer

    package = read_package(maya_inputs)
    package.claim.value = 4.2
    replay, _ = _build_replay_report(package, Tracer())
    assessment = Assessment(
        package=package,
        provenance=check_provenance(package),
        replay=replay,
    )
    outcome = apply_rules(assessment)
    assert outcome.rule_id == "R-003"
    assert "algebraic" in outcome.headline


def test_every_rule_outcome_carries_a_finding(maya_inputs, adversarial):
    paths = [
        maya_inputs,
        adversarial / "case_a_stale_artifact" / "inputs",
        adversarial / "case_c_missing_evidence" / "inputs",
        adversarial / "case_d_human_decision" / "inputs",
        adversarial / "case_e_clean_pass" / "inputs",
    ]
    from agent.researchops_agent import verify_package

    for path in paths:
        card = verify_package(path).card
        assert card.fired_rule
        assert card.findings
        assert card.findings[-1].check_id == card.fired_rule
        if card.verdict is Verdict.ALLOW:
            assert card.findings[-1].severity is Severity.INFO


def test_rule_table_always_returns_an_outcome(adversarial):
    # The fallback exists so that an unforeseen combination is escalated, not
    # silently allowed.
    from policy.verdict_rules import _FALLBACK

    assert _FALLBACK.verdict is Verdict.REVIEW
    assert _FALLBACK.claim_state is ClaimState.UNVERIFIED
