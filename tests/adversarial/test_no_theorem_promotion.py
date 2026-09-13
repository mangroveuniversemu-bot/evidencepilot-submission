"""The agent is not allowed to turn evidence into a theorem."""

from __future__ import annotations

import pytest

from agent.schemas import ClaimState, EvidenceClass, Verdict
from evidence.certificate import (
    TheoremPromotionError,
    assert_no_theorem_promotion,
    finite_verification_card,
    issue_finite_certificate,
    verify_signature,
)
from policy.claim_states import UnsupportedClaimState, assert_supported
from tools.benchmark_runner import FINITE_VERIFICATION_LIMITATION, verify_collatz


@pytest.fixture(scope="module")
def collatz():
    result = verify_collatz(20_000)
    card = finite_verification_card(result, "the Collatz conjecture")
    return result, card, issue_finite_certificate(card, result)


def test_finite_search_finds_no_counterexample(collatz):
    result, _, _ = collatz
    assert result.passed
    assert result.cases_tested == 20_000


def test_the_verdict_leaves_the_question_open(collatz):
    _, card, _ = collatz
    assert card.evidence_class is EvidenceClass.FINITE_VERIFICATION
    assert card.claim_state is ClaimState.INCONCLUSIVE
    assert card.verdict is Verdict.REVIEW
    assert "remains open" in card.headline


def test_the_certificate_states_the_limit_explicitly(collatz):
    _, _, certificate = collatz
    assert FINITE_VERIFICATION_LIMITATION in certificate.limitations
    assert any("untested" in line for line in certificate.limitations)
    assert verify_signature(certificate)


def test_a_certificate_cannot_claim_a_finite_search_proved_anything(collatz):
    _, card, certificate = collatz
    promoted = certificate.model_copy(
        update={
            "verdict_card": card.model_copy(
                update={"headline": "The Collatz conjecture is proven for every integer."}
            )
        }
    )
    with pytest.raises(TheoremPromotionError):
        assert_no_theorem_promotion(promoted)


def test_dropping_the_limitation_is_rejected(collatz):
    _, _, certificate = collatz
    stripped = certificate.model_copy(
        update={
            "limitations": tuple(
                line for line in certificate.limitations if line != FINITE_VERIFICATION_LIMITATION
            )
        }
    )
    with pytest.raises(TheoremPromotionError, match="must carry the limitation"):
        assert_no_theorem_promotion(stripped)


def test_finite_evidence_can_never_reach_reproduced():
    with pytest.raises(UnsupportedClaimState):
        assert_supported(ClaimState.REPRODUCED, EvidenceClass.FINITE_VERIFICATION)


def test_a_counterexample_would_refute_rather_than_prove():
    from agent.schemas import BenchmarkResult

    fake = BenchmarkResult(
        benchmark_id="collatz-finite-fake",
        limit=10,
        cases_tested=10,
        counterexamples=(7,),
        max_steps=1,
        max_peak=1,
        elapsed_s=0.0,
    )
    card = finite_verification_card(fake, "the Collatz conjecture")
    assert card.claim_state is ClaimState.NOT_REPRODUCED
    assert card.verdict is Verdict.BLOCK
    assert "Counterexample" in card.headline


def test_real_verdicts_never_contain_promotion_language(repo_root):
    from agent.researchops_agent import verify_package

    for relative in (
        "maya_case/inputs",
        "adversarial/case_a_stale_artifact/inputs",
        "adversarial/case_c_missing_evidence/inputs",
        "adversarial/case_d_human_decision/inputs",
        "adversarial/case_e_clean_pass/inputs",
    ):
        certificate = verify_package(repo_root / "examples" / relative).certificate
        assert_no_theorem_promotion(certificate)  # raises on failure
