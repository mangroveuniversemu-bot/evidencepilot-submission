"""What a claim is allowed to be called, given the evidence actually gathered.

This is the guard against the most tempting failure mode in a verification
agent: letting a clean run of a small computation turn into a confident
statement about the world.
"""

from __future__ import annotations

from agent.schemas import ClaimState, EvidenceClass

#: Which claim states each class of evidence can support.
SUPPORTED_STATES: dict[EvidenceClass, frozenset[ClaimState]] = {
    EvidenceClass.NONE: frozenset({ClaimState.UNVERIFIED}),
    EvidenceClass.DETERMINISTIC_RECOMPUTE: frozenset(
        {
            ClaimState.UNVERIFIED,
            ClaimState.REPRODUCED,
            ClaimState.NOT_REPRODUCED,
            ClaimState.INCONCLUSIVE,
        }
    ),
    EvidenceClass.STATISTICAL_REPLAY: frozenset(
        {
            ClaimState.UNVERIFIED,
            ClaimState.REPRODUCED,
            ClaimState.NOT_REPRODUCED,
            ClaimState.INCONCLUSIVE,
        }
    ),
    # A finite search can refute (by counterexample) or fail to refute. It can
    # never establish a universal statement, so REPRODUCED is not available.
    EvidenceClass.FINITE_VERIFICATION: frozenset(
        {ClaimState.UNVERIFIED, ClaimState.NOT_REPRODUCED, ClaimState.INCONCLUSIVE}
    ),
}

LEGAL_TRANSITIONS: dict[ClaimState, frozenset[ClaimState]] = {
    ClaimState.UNVERIFIED: frozenset(
        {
            ClaimState.UNVERIFIED,
            ClaimState.REPRODUCED,
            ClaimState.NOT_REPRODUCED,
            ClaimState.INCONCLUSIVE,
        }
    ),
    # A settled claim can only be reopened by going back through UNVERIFIED,
    # which forces a fresh package and a fresh certificate.
    ClaimState.REPRODUCED: frozenset({ClaimState.REPRODUCED, ClaimState.UNVERIFIED}),
    ClaimState.NOT_REPRODUCED: frozenset({ClaimState.NOT_REPRODUCED, ClaimState.UNVERIFIED}),
    ClaimState.INCONCLUSIVE: frozenset(
        {
            ClaimState.INCONCLUSIVE,
            ClaimState.UNVERIFIED,
            ClaimState.REPRODUCED,
            ClaimState.NOT_REPRODUCED,
        }
    ),
}


class UnsupportedClaimState(ValueError):
    """Raised when a claim state claims more than the evidence can carry."""


def assert_supported(state: ClaimState, evidence_class: EvidenceClass) -> None:
    allowed = SUPPORTED_STATES[evidence_class]
    if state not in allowed:
        raise UnsupportedClaimState(
            f"{evidence_class.value} evidence cannot support claim state {state.value}; "
            f"allowed: {', '.join(sorted(s.value for s in allowed))}"
        )


def assert_legal_transition(current: ClaimState, proposed: ClaimState) -> None:
    if proposed not in LEGAL_TRANSITIONS[current]:
        raise UnsupportedClaimState(
            f"illegal claim-state transition {current.value} -> {proposed.value}"
        )
