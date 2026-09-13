"""The whole chain, on the packages shipped in this repository."""

from __future__ import annotations

import pytest

from agent.researchops_agent import verify_package
from agent.schemas import ClaimState, EvidenceClass, Verdict
from evidence.certificate import verify_signature

CASES = {
    "maya_case/inputs": (Verdict.BLOCK, ClaimState.NOT_REPRODUCED, "R-005"),
    "adversarial/case_a_stale_artifact/inputs": (Verdict.BLOCK, ClaimState.UNVERIFIED, "R-002"),
    "adversarial/case_c_missing_evidence/inputs": (Verdict.REVIEW, ClaimState.REPRODUCED, "R-007"),
    "adversarial/case_d_human_decision/inputs": (
        Verdict.HUMAN_DECISION,
        ClaimState.INCONCLUSIVE,
        "R-006",
    ),
    "adversarial/case_e_clean_pass/inputs": (Verdict.ALLOW, ClaimState.REPRODUCED, "R-009"),
    "adversarial/case_g_prompt_injection/inputs": (
        Verdict.BLOCK,
        ClaimState.NOT_REPRODUCED,
        "R-005",
    ),
    "adversarial/case_h_unphysical_claim/inputs": (
        Verdict.BLOCK,
        ClaimState.NOT_REPRODUCED,
        "R-005",
    ),
    "adversarial/case_i_unphysical_convention/inputs": (
        Verdict.BLOCK,
        ClaimState.UNVERIFIED,
        "R-004",
    ),
    "adversarial/case_j_incomplete_counts/inputs": (
        Verdict.BLOCK,
        ClaimState.UNVERIFIED,
        "R-001",
    ),
    "adversarial/case_k_missing_environment/inputs": (
        Verdict.REVIEW,
        ClaimState.REPRODUCED,
        "R-008",
    ),
    "adversarial/case_l_finite_sample_boundary/inputs": (
        Verdict.REVIEW,
        ClaimState.REPRODUCED,
        "R-010",
    ),
    "adversarial/case_m_algebraic_claim/inputs": (
        Verdict.BLOCK,
        ClaimState.NOT_REPRODUCED,
        "R-003",
    ),
}


@pytest.mark.parametrize("relative,expected", CASES.items())
def test_each_example_lands_on_its_intended_verdict(repo_root, relative, expected):
    card = verify_package(repo_root / "examples" / relative).card
    assert (card.verdict, card.claim_state, card.fired_rule) == expected


@pytest.mark.parametrize("relative", CASES)
def test_certificates_are_signed_and_self_consistent(repo_root, relative):
    certificate = verify_package(repo_root / "examples" / relative).certificate
    assert certificate.signature
    assert verify_signature(certificate)
    tampered = certificate.model_copy(
        update={
            "verdict_card": certificate.verdict_card.model_copy(
                update={"headline": "everything is fine"}
            )
        }
    )
    assert not verify_signature(tampered)


@pytest.mark.parametrize("relative", CASES)
def test_every_run_records_a_trace_and_input_hashes(repo_root, relative):
    run = verify_package(repo_root / "examples" / relative)
    assert run.trace.steps
    assert run.trace.steps[0].tool == "artifact_reader.read_package"
    assert [s.index for s in run.trace.steps] == list(range(1, len(run.trace.steps) + 1))
    assert "raw_counts.csv" in run.certificate.input_hashes


def test_verification_is_deterministic(maya_inputs):
    first = verify_package(maya_inputs)
    second = verify_package(maya_inputs)
    assert first.card.model_dump() == second.card.model_dump()
    # Only the certificate identity and timestamp may differ between runs.
    assert first.certificate.model_dump(
        exclude={"certificate_id", "issued_at", "signature", "trace"}
    ) == second.certificate.model_dump(
        exclude={"certificate_id", "issued_at", "signature", "trace"}
    )


def test_stale_input_short_circuits_the_replay(repo_root):
    run = verify_package(repo_root / "examples/adversarial/case_a_stale_artifact/inputs")
    assert run.assessment.replay is None
    assert run.card.evidence_class is EvidenceClass.NONE
    skipped = [s for s in run.trace.steps if s.outcome == "skipped"]
    assert skipped and skipped[0].tool == "chsh_replay.compute_chsh"
