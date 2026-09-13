"""Product invariants about what is allowed to reach a person."""

from __future__ import annotations

import pytest

from agent.researchops_agent import verify_package
from agent.schemas import Verdict
from policy.escalation import EscalationPolicyViolation, assert_escalation_invariants

ALL_CASES = [
    "maya_case/inputs",
    "adversarial/case_a_stale_artifact/inputs",
    "adversarial/case_c_missing_evidence/inputs",
    "adversarial/case_d_human_decision/inputs",
    "adversarial/case_e_clean_pass/inputs",
]


@pytest.mark.parametrize("relative", ALL_CASES)
def test_at_most_one_escalation_per_claim(repo_root, relative):
    card = verify_package(repo_root / "examples" / relative).card
    # The type system allows exactly zero or one; this pins the semantics too.
    assert card.escalation is None or card.escalation.escalation_id.endswith(card.claim_id)


@pytest.mark.parametrize("relative", ALL_CASES)
def test_every_option_states_its_consequence(repo_root, relative):
    card = verify_package(repo_root / "examples" / relative).card
    if card.escalation is None:
        return
    assert len(card.escalation.options) >= 2
    for option in card.escalation.options:
        assert option.label.strip()
        assert option.consequence.strip()


def test_allow_never_escalates(repo_root):
    card = verify_package(repo_root / "examples/adversarial/case_e_clean_pass/inputs").card
    assert card.verdict is Verdict.ALLOW
    assert card.escalation is None


def test_human_decision_carries_no_recommendation(repo_root):
    card = verify_package(repo_root / "examples/adversarial/case_d_human_decision/inputs").card
    assert card.verdict is Verdict.HUMAN_DECISION
    assert card.escalation is not None
    assert card.escalation.recommended_option_id is None


def test_a_recommendation_on_a_human_decision_is_rejected(repo_root):
    from policy.verdict_rules import apply_rules

    run = verify_package(repo_root / "examples/adversarial/case_d_human_decision/inputs")
    outcome = apply_rules(run.assessment)
    bad = run.card.escalation.model_copy(update={"recommended_option_id": "INCLUDE_FLAGGED"})
    with pytest.raises(EscalationPolicyViolation):
        assert_escalation_invariants(bad, outcome)


def test_a_recommendation_must_be_one_of_the_options(repo_root):
    from policy.verdict_rules import apply_rules

    run = verify_package(repo_root / "examples/maya_case/inputs")
    outcome = apply_rules(run.assessment)
    bad = run.card.escalation.model_copy(update={"recommended_option_id": "DO_WHATEVER"})
    with pytest.raises(EscalationPolicyViolation):
        assert_escalation_invariants(bad, outcome)
