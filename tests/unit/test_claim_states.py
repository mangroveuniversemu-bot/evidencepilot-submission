"""The guard that stops evidence from being promoted into a theorem."""

from __future__ import annotations

import pytest

from agent.schemas import ClaimState, EvidenceClass
from policy.claim_states import (
    UnsupportedClaimState,
    assert_legal_transition,
    assert_supported,
)


def test_there_is_no_proof_evidence_class():
    assert "PROOF" not in EvidenceClass.__members__


def test_finite_verification_cannot_reproduce_a_universal_claim():
    with pytest.raises(UnsupportedClaimState):
        assert_supported(ClaimState.REPRODUCED, EvidenceClass.FINITE_VERIFICATION)


def test_finite_verification_can_refute():
    assert_supported(ClaimState.NOT_REPRODUCED, EvidenceClass.FINITE_VERIFICATION)
    assert_supported(ClaimState.INCONCLUSIVE, EvidenceClass.FINITE_VERIFICATION)


def test_no_evidence_supports_only_unverified():
    assert_supported(ClaimState.UNVERIFIED, EvidenceClass.NONE)
    for state in (ClaimState.REPRODUCED, ClaimState.NOT_REPRODUCED, ClaimState.INCONCLUSIVE):
        with pytest.raises(UnsupportedClaimState):
            assert_supported(state, EvidenceClass.NONE)


def test_settled_claims_cannot_flip_without_reopening():
    with pytest.raises(UnsupportedClaimState):
        assert_legal_transition(ClaimState.REPRODUCED, ClaimState.NOT_REPRODUCED)
    assert_legal_transition(ClaimState.REPRODUCED, ClaimState.UNVERIFIED)
    assert_legal_transition(ClaimState.UNVERIFIED, ClaimState.NOT_REPRODUCED)
