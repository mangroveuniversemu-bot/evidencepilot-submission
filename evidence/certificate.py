"""Issue a signed record of what was checked, and refuse to overstate it.

A certificate is the artifact that outlives the conversation. It therefore has
to be conservative in a way a chat reply does not: every certificate states its
own limitations, and a certificate backed only by a finite search is forbidden
from reading as a proof.
"""

from __future__ import annotations

import hashlib
import json
import uuid

from agent.schemas import (
    BenchmarkResult,
    ClaimState,
    EvidenceCertificate,
    EvidenceClass,
    ExecutionTrace,
    Verdict,
    VerdictCard,
)
from agent.state import Assessment
from evidence.execution_trace import utc_now
from policy.claim_states import assert_supported
from tools.benchmark_runner import FINITE_VERIFICATION_LIMITATION

TOOL_VERSIONS = {"evidencepilot": "0.1.0", "chsh_replay": "2", "verdict_rules": "2"}

#: Language a certificate is never allowed to contain. These are the phrasings
#: that turn evidence into a theorem.
PROMOTION_PHRASES: tuple[str, ...] = (
    "is proved",
    "is proven",
    "proves the",
    "proof that",
    "establishes the theorem",
    "conjecture is true",
    "conjecture verified",
    "holds for all",
    "always holds",
    "quantum mechanics is confirmed",
)

BASE_LIMITATIONS: tuple[str, ...] = (
    "This certificate records a finite, deterministic replay of the artifacts supplied. "
    "It is a statement about those artifacts, not about nature.",
    "A reproduced claim agrees with replay within the configured tolerance under the "
    "registered convention. It does not establish exact arithmetic equality or that the "
    "experiment was sound.",
)

CHSH_LIMITATION = (
    "Physical interpretation is not established. The reported standard error is a plug-in "
    "estimate under independent-sampling assumptions, not a finite-sample confidence "
    "interval or a loophole-free Bell-test certification. A zero plug-in standard error "
    "does not establish zero population uncertainty."
)


class TheoremPromotionError(AssertionError):
    """Raised when certificate text would upgrade evidence into a theorem."""


def assert_no_theorem_promotion(certificate: EvidenceCertificate) -> None:
    """Scan the human-readable fields of a certificate for overstatement."""
    text_fields = [certificate.verdict_card.headline, certificate.verdict_card.root_cause or ""]
    if certificate.verdict_card.escalation is not None:
        text_fields.append(certificate.verdict_card.escalation.question)
        text_fields.append(certificate.verdict_card.escalation.context)
    text_fields.extend(finding.summary for finding in certificate.verdict_card.findings)
    haystack = " ".join(text_fields).lower()
    for phrase in PROMOTION_PHRASES:
        if phrase in haystack:
            raise TheoremPromotionError(
                f"certificate {certificate.certificate_id} contains promotion phrase {phrase!r}"
            )

    if certificate.verdict_card.evidence_class is EvidenceClass.FINITE_VERIFICATION:
        if FINITE_VERIFICATION_LIMITATION not in certificate.limitations:
            raise TheoremPromotionError(
                "a finite-verification certificate must carry the limitation "
                f"{FINITE_VERIFICATION_LIMITATION!r}"
            )
        if certificate.verdict_card.claim_state is ClaimState.REPRODUCED:
            raise TheoremPromotionError(
                "a finite search can never put a universal claim in state REPRODUCED"
            )


def sign(certificate: EvidenceCertificate) -> str:
    payload = certificate.model_dump(mode="json", exclude={"signature"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def issue_certificate(
    assessment: Assessment,
    card: VerdictCard,
    trace: ExecutionTrace | None = None,
    input_hashes: dict[str, str] | None = None,
) -> EvidenceCertificate:
    assert_supported(card.claim_state, card.evidence_class)

    limitations = [*BASE_LIMITATIONS, CHSH_LIMITATION]
    if card.verdict is Verdict.BLOCK:
        limitations.append(
            "A BLOCK verdict means this submission cannot be accepted by the verifier; see "
            "claim_state for whether replay failed or was not validly assessable. It is not a "
            "finding of error by the submitter and not a statement that the underlying physics "
            "is wrong."
        )
    if card.verdict is Verdict.HUMAN_DECISION:
        limitations.append(
            "Both analyses recorded here are arithmetically correct. The agent deliberately "
            "records no preference between them."
        )
    if assessment.root_cause is not None and assessment.root_cause.identified is None:
        limitations.append(
            "No single deviation from the registered convention explains the disagreement, so "
            "the root cause named here is a candidate, not a determination."
        )

    certificate = EvidenceCertificate(
        certificate_id=f"CERT-{uuid.uuid4().hex[:12]}",
        issued_at=utc_now(),
        package_id=assessment.package_id,
        claim_id=assessment.claim_id,
        verdict_card=card,
        input_hashes=input_hashes or {},
        convention_id=assessment.package.convention.convention_id,
        tool_versions=dict(TOOL_VERSIONS),
        trace=trace,
        limitations=tuple(limitations),
    )
    assert_no_theorem_promotion(certificate)
    return certificate.model_copy(update={"signature": sign(certificate)})


def verify_signature(certificate: EvidenceCertificate) -> bool:
    return certificate.signature == sign(certificate)


def finite_verification_card(result: BenchmarkResult, claim: str) -> VerdictCard:
    """Build the deliberately unexciting verdict a finite search is allowed to produce."""
    if result.passed:
        headline = (
            f"No counterexample to {claim} for n <= {result.limit:,}. The claim remains open."
        )
        state = ClaimState.INCONCLUSIVE
        verdict = Verdict.REVIEW
    else:
        headline = f"Counterexample found for {claim}: n = {result.counterexamples[0]}."
        state = ClaimState.NOT_REPRODUCED
        verdict = Verdict.BLOCK
    return VerdictCard(
        verdict=verdict,
        claim_state=state,
        evidence_class=EvidenceClass.FINITE_VERIFICATION,
        claim_id=result.benchmark_id,
        headline=headline,
        numbers={
            "limit": float(result.limit),
            "cases_tested": float(result.cases_tested),
            "max_steps": float(result.max_steps),
            "max_peak": float(result.max_peak),
        },
        fired_rule="FINITE-001",
    )


def issue_finite_certificate(
    card: VerdictCard, result: BenchmarkResult, trace: ExecutionTrace | None = None
) -> EvidenceCertificate:
    """Certify a finite search without letting it read as a theorem."""
    limitations = list(BASE_LIMITATIONS)
    limitations.append(FINITE_VERIFICATION_LIMITATION)
    limitations.append(
        f"Exactly {result.cases_tested:,} cases were checked (n <= {result.limit:,}). "
        "Every integer above that limit is untested. A universal statement about all "
        "integers does not follow from any finite search, however large."
    )
    certificate = EvidenceCertificate(
        certificate_id=f"CERT-{uuid.uuid4().hex[:12]}",
        issued_at=utc_now(),
        package_id=result.benchmark_id,
        claim_id=result.benchmark_id,
        verdict_card=card,
        tool_versions=dict(TOOL_VERSIONS),
        trace=trace,
        limitations=tuple(limitations),
    )
    assert_no_theorem_promotion(certificate)
    return certificate.model_copy(update={"signature": sign(certificate)})
