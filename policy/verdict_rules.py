"""The deterministic rule table that turns an assessment into a verdict.

Rules are ordered and the first match wins. Ordering is the policy: a stale
input outranks a disagreement, because a disagreement computed against the
wrong dataset is meaningless.

No language model participates in this file.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agent.schemas import (
    ClaimState,
    EvidenceClass,
    Finding,
    PhysicalInterpretation,
    Severity,
    Verdict,
)
from agent.state import Assessment
from policy.claim_states import assert_supported

#: A replay is treated as agreeing with a claim when it lands within this many
#: standard deviations, or within the claim's own stated precision.
AGREEMENT_SIGMA = 3.0


@dataclass(frozen=True)
class RuleOutcome:
    rule_id: str
    verdict: Verdict
    claim_state: ClaimState
    headline: str
    finding: Finding


@dataclass(frozen=True)
class Rule:
    rule_id: str
    description: str
    evaluate: Callable[[Assessment], RuleOutcome | None]


def _r001_unreplayable(a: Assessment) -> RuleOutcome | None:
    if a.replay_error is None:
        return None
    return RuleOutcome(
        rule_id="R-001",
        verdict=Verdict.BLOCK,
        claim_state=ClaimState.UNVERIFIED,
        headline="The submitted package cannot be replayed.",
        finding=Finding(
            check_id="R-001",
            severity=Severity.CRITICAL,
            summary="Independent replay could not run.",
            detail=a.replay_error,
        ),
    )


def _r002_input_integrity(a: Assessment) -> RuleOutcome | None:
    critical = a.provenance.critical
    if not critical:
        return None
    first = critical[0]
    return RuleOutcome(
        rule_id="R-002",
        verdict=Verdict.BLOCK,
        claim_state=ClaimState.UNVERIFIED,
        headline="Input integrity failed; the claim was not replayed.",
        finding=Finding(
            check_id="R-002",
            severity=Severity.CRITICAL,
            summary=first.summary,
            detail=first.detail,
            evidence=dict(first.evidence),
        ),
    )


def _r003_claim_out_of_range(a: Assessment) -> RuleOutcome | None:
    if a.replay is None or a.replay.diagnostics is None:
        return None
    diagnostics = a.replay.diagnostics
    bound = diagnostics.algebraic_bound
    claimed = a.package.claim.value
    if diagnostics.claim_in_algebraic_range:
        return None
    return RuleOutcome(
        rule_id="R-003",
        verdict=Verdict.BLOCK,
        claim_state=ClaimState.NOT_REPRODUCED,
        headline=f"The claimed value {claimed:.4f} is outside the CHSH algebraic range.",
        finding=Finding(
            check_id="R-003",
            severity=Severity.CRITICAL,
            summary="The submitted statistic is outside the range of four signed correlations.",
            detail=(
                "For the checked CHSH definition, four empirical correlations in [-1, 1] "
                "give |S| <= 4. This is an arithmetic range check, not a quantum hypothesis test."
            ),
            evidence={"claimed": claimed, "algebraic_bound": bound},
        ),
    )


def _r004_invalid_convention(a: Assessment) -> RuleOutcome | None:
    if a.replay is None:
        return None
    diagnostics = a.replay.diagnostics
    if diagnostics is not None and diagnostics.convention_valid:
        return None
    return RuleOutcome(
        rule_id="R-004",
        verdict=Verdict.BLOCK,
        claim_state=ClaimState.UNVERIFIED,
        headline="The convention has not passed the supported CHSH definition checks.",
        finding=Finding(
            check_id="R-004",
            severity=Severity.CRITICAL,
            summary="Arithmetic on an unsupported expression is not a CHSH verification.",
            detail=(
                "Review the convention file: " + " ".join(diagnostics.convention_issues)
                if diagnostics
                else "The required definition diagnostics are missing."
            ),
        ),
    )


def _r005_replay_disagreement(a: Assessment) -> RuleOutcome | None:
    if a.replay is None or a.replay.agrees:
        return None
    replay = a.replay
    root = a.root_cause.conclusion if a.root_cause else "No root-cause search was run."
    scale = (
        f"Difference {replay.delta_s:+.4f} is {abs(replay.delta_in_sigma):.1f} times the "
        "plug-in standard error. "
        if replay.delta_in_sigma is not None
        else f"Difference {replay.delta_s:+.4f}; a sigma ratio is undefined because the "
        "plug-in standard error is zero. "
    )
    return RuleOutcome(
        rule_id="R-005",
        verdict=Verdict.BLOCK,
        claim_state=ClaimState.NOT_REPRODUCED,
        headline=(
            f"Claim states {replay.claimed_value:.4f}; independent replay gives "
            f"{replay.registered.s_value:.4f} +/- {replay.registered.sigma_s:.4f}."
        ),
        finding=Finding(
            check_id="R-005",
            severity=Severity.CRITICAL,
            summary="The claim was not reproduced under the registered convention.",
            detail=(
                scale + "Both analyses read the same raw counts, so the gap is "
                f"systematic, not statistical. {root}"
            ),
            evidence={
                "claimed": replay.claimed_value,
                "replayed": replay.registered.s_value,
                "sigma": replay.registered.sigma_s,
                "delta_in_sigma": replay.delta_in_sigma,
            },
        ),
    )


def _r006_conclusion_not_robust(a: Assessment) -> RuleOutcome | None:
    if a.replay is None or a.replay.robustness_alternative is None:
        return None
    primary = a.replay.registered
    alternative = a.replay.robustness_alternative
    if primary.violates_bound == alternative.violates_bound:
        return None
    excluded = alternative.excluded_subruns or primary.excluded_subruns
    return RuleOutcome(
        rule_id="R-006",
        verdict=Verdict.HUMAN_DECISION,
        claim_state=ClaimState.INCONCLUSIVE,
        headline=("The conclusion flips depending on a documented, unresolved data-quality flag."),
        finding=Finding(
            check_id="R-006",
            severity=Severity.WARN,
            summary="Both inclusion choices are defensible and they disagree about the bound.",
            detail=(
                f"Including the flagged sub-run(s) gives S={primary.s_value:.4f} "
                f"+/- {primary.sigma_s:.4f} ({primary.sigma_above_bound:+.1f} sigma vs the "
                f"classical bound). Excluding them gives S={alternative.s_value:.4f} "
                f"+/- {alternative.sigma_s:.4f} ({alternative.sigma_above_bound:+.1f} sigma). "
                "Choosing between them is a scientific judgement about instrument behaviour, "
                "not a computation."
            ),
            evidence={
                "flagged_subruns": list(excluded),
                "s_including": primary.s_value,
                "s_excluding": alternative.s_value,
            },
        ),
    )


def _r007_convention_unregistered(a: Assessment) -> RuleOutcome | None:
    if a.package.convention.is_registered:
        return None
    return RuleOutcome(
        rule_id="R-007",
        verdict=Verdict.REVIEW,
        claim_state=ClaimState.REPRODUCED,
        headline="The claim replays, but against an unregistered convention.",
        finding=Finding(
            check_id="R-007",
            severity=Severity.WARN,
            summary="Reproduction is not certification.",
            detail=(
                f"Convention {a.package.convention.convention_id} has no registry entry, so the "
                "replay only shows that the claim is self-consistent, not that it follows an "
                "agreed standard."
            ),
        ),
    )


def _r008_provenance_incomplete(a: Assessment) -> RuleOutcome | None:
    warnings = a.provenance.warnings
    if not warnings:
        return None
    return RuleOutcome(
        rule_id="R-008",
        verdict=Verdict.REVIEW,
        claim_state=ClaimState.REPRODUCED,
        headline="The claim replays, but its provenance record is incomplete.",
        finding=Finding(
            check_id="R-008",
            severity=Severity.WARN,
            summary=f"{len(warnings)} provenance check(s) are incomplete.",
            detail="; ".join(f.summary for f in warnings),
            evidence={"checks": [f.check_id for f in warnings]},
        ),
    )


def _r009_verified(a: Assessment) -> RuleOutcome | None:
    if a.replay is None:
        return None
    result = a.replay.registered
    verdict_word = "passes" if result.violates_bound else "does not pass"
    return RuleOutcome(
        rule_id="R-009",
        verdict=Verdict.ALLOW,
        claim_state=ClaimState.REPRODUCED,
        headline=(
            f"Claim reproduced: S={result.s_value:.4f} +/- {result.sigma_s:.4f}, which "
            f"{verdict_word} the approximate three-sigma classical-bound screen. "
            "Physical interpretation is not established."
        ),
        finding=Finding(
            check_id="R-009",
            severity=Severity.INFO,
            summary="Replay agrees within the configured tolerance and provenance is complete.",
            evidence={
                "s_value": result.s_value,
                "sigma_s": result.sigma_s,
                "sigma_above_bound": result.sigma_above_bound,
            },
        ),
    )


def _r010_finite_sample_review(a: Assessment) -> RuleOutcome | None:
    if a.replay is None or a.replay.diagnostics is None:
        return None
    d = a.replay.diagnostics
    if not (d.empirical_above_tsirelson or d.degenerate_uncertainty):
        return None
    return RuleOutcome(
        rule_id="R-010",
        verdict=Verdict.REVIEW,
        claim_state=ClaimState.REPRODUCED,
        headline="The number reproduces; finite-sample interpretation requires review.",
        finding=Finding(
            check_id="R-010",
            severity=Severity.WARN,
            summary="Numerical reproduction does not establish a physical conclusion.",
            detail=(
                "The empirical statistic exceeds the quantum expectation bound or a pair has "
                "degenerate plug-in uncertainty. Finite samples can fluctuate beyond an "
                "expectation bound. Zero plug-in variance is not zero population uncertainty. "
                "Review sampling assumptions and an appropriate finite-sample analysis; this "
                "verifier does not certify a Bell violation or an impossible quantum state."
            ),
            evidence=d.model_dump(mode="json"),
        ),
    )


RULES: tuple[Rule, ...] = (
    Rule("R-001", "The package could not be replayed at all.", _r001_unreplayable),
    Rule("R-002", "Declared inputs do not match supplied inputs.", _r002_input_integrity),
    Rule("R-004", "The expression is not a supported CHSH definition.", _r004_invalid_convention),
    Rule("R-003", "The claim exceeds the algebraic range.", _r003_claim_out_of_range),
    Rule("R-005", "Independent replay contradicts the claim.", _r005_replay_disagreement),
    Rule(
        "R-006",
        "The conclusion is not robust to a data-quality flag.",
        _r006_conclusion_not_robust,
    ),
    Rule("R-007", "The analysis convention is unregistered.", _r007_convention_unregistered),
    Rule("R-008", "The provenance record is incomplete.", _r008_provenance_incomplete),
    Rule(
        "R-010", "Finite-sample physical interpretation needs review.", _r010_finite_sample_review
    ),
    Rule("R-009", "Everything checks out.", _r009_verified),
)

_FALLBACK = RuleOutcome(
    rule_id="R-000",
    verdict=Verdict.REVIEW,
    claim_state=ClaimState.UNVERIFIED,
    headline="No rule matched this assessment.",
    finding=Finding(
        check_id="R-000",
        severity=Severity.WARN,
        summary="The rule table did not cover this case; a human must look.",
    ),
)


def evidence_class_for(assessment: Assessment) -> EvidenceClass:
    if assessment.replay is None:
        return EvidenceClass.NONE
    if assessment.replay.diagnostics is None or not assessment.replay.diagnostics.convention_valid:
        return EvidenceClass.DETERMINISTIC_RECOMPUTE
    return EvidenceClass.STATISTICAL_REPLAY


def physical_interpretation_for(assessment: Assessment) -> PhysicalInterpretation:
    if assessment.replay is None or assessment.replay.diagnostics is None:
        return PhysicalInterpretation.NOT_ASSESSED
    d = assessment.replay.diagnostics
    if not d.convention_valid:
        return PhysicalInterpretation.NOT_ASSESSED
    if d.empirical_above_tsirelson or d.degenerate_uncertainty:
        return PhysicalInterpretation.REQUIRES_REVIEW
    return PhysicalInterpretation.NOT_ESTABLISHED


def apply_rules(assessment: Assessment) -> RuleOutcome:
    """Return the first rule outcome that fires. Never returns None."""
    for rule in RULES:
        outcome = rule.evaluate(assessment)
        if outcome is not None:
            assert_supported(outcome.claim_state, evidence_class_for(assessment))
            return outcome
    return _FALLBACK
