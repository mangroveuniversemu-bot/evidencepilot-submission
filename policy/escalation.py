"""Decide what, if anything, is worth a person's attention.

Two invariants, both tested:

* A claim produces at most one escalation. Verification that surfaces three
  questions has not done its job.
* A HUMAN_DECISION escalation carries no recommendation. If the agent had
  grounds to recommend, the case would not have been a human decision.
"""

from __future__ import annotations

from agent.schemas import Escalation, EscalationOption, Verdict
from agent.state import Assessment
from policy.verdict_rules import RuleOutcome


def _option(option_id: str, label: str, consequence: str) -> EscalationOption:
    return EscalationOption(option_id=option_id, label=label, consequence=consequence)


EscalationDraft = tuple[str, str, list[EscalationOption], str | None]


def _blocked_by_disagreement(assessment: Assessment) -> EscalationDraft:
    replay = assessment.replay
    assert replay is not None
    result = replay.registered
    corrected = "does not pass" if not result.violates_bound else "passes"
    root = assessment.root_cause.conclusion if assessment.root_cause else ""
    question = (
        f"Claim {assessment.claim_id} does not reproduce under the registered convention. "
        "How should it be handled?"
    )
    context = (
        f"Submitted: S = {replay.claimed_value:.4f}. "
        f"Independent replay: S = {result.s_value:.4f} +/- {result.sigma_s:.4f}. "
        f"{root}"
    )
    options = [
        _option(
            "RERUN_UNDER_REGISTERED_CONVENTION",
            "Re-run the analysis with the registered convention applied, then resubmit.",
            (
                f"The corrected statistic is S = {result.s_value:.4f} +/- {result.sigma_s:.4f}, "
                f"which {corrected} the approximate classical-bound screen. "
                "This does not certify a physical interpretation."
            ),
        ),
        _option(
            "EXCLUDE_RUN",
            "Exclude this run from the review and leave the claim open.",
            "No result is presented for this dataset; the disagreement stays unresolved.",
        ),
        _option(
            "OVERRIDE_WITH_JUSTIFICATION",
            "Present the claim as submitted, with a written justification.",
            (
                "Requires a written justification in a separate decision record. "
                "The original certificate remains BLOCK / NOT_REPRODUCED. "
                "Recording this intent does not authorize the claim or execute an override."
            ),
        ),
    ]
    return question, context, options, "RERUN_UNDER_REGISTERED_CONVENTION"


def _blocked_by_integrity(assessment: Assessment) -> EscalationDraft:
    question = (
        f"Claim {assessment.claim_id} was computed against different inputs than the ones "
        "supplied. How should it be handled?"
    )
    critical = assessment.provenance.critical
    fallback = "Declared inputs do not match supplied inputs."
    context = critical[0].detail if critical else fallback
    options = [
        _option(
            "REQUEST_MATCHING_PACKAGE",
            "Ask the submitter to resubmit with the dataset the claim was actually computed on.",
            "Verification restarts once a self-consistent package arrives. "
            "Nothing is presented today.",
        ),
        _option(
            "RECOMPUTE_ON_SUPPLIED_DATASET",
            "Recompute the statistic on the dataset supplied here and treat that as the claim.",
            "Produces a defensible number, but it is a new result, not a reproduction "
            "of the claim.",
        ),
        _option(
            "EXCLUDE_RUN",
            "Exclude this run from the review.",
            "No result is presented for this dataset.",
        ),
    ]
    return question, context, options, "REQUEST_MATCHING_PACKAGE"


def _human_decision(assessment: Assessment) -> EscalationDraft:
    replay = assessment.replay
    assert replay is not None and replay.robustness_alternative is not None
    including = replay.registered
    excluding = replay.robustness_alternative
    flagged = excluding.excluded_subruns or including.excluded_subruns
    question = (
        f"Claim {assessment.claim_id} reproduces, but its conclusion depends on whether a "
        f"flagged acquisition sub-run is used. Which analysis stands?"
    )
    context = (
        f"Flagged sub-run(s): {', '.join(flagged) or 'none recorded'}. "
        f"Including them: S = {including.s_value:.4f} +/- {including.sigma_s:.4f} "
        f"({including.sigma_above_bound:+.1f} sigma vs the classical bound). "
        f"Excluding them: S = {excluding.s_value:.4f} +/- {excluding.sigma_s:.4f} "
        f"({excluding.sigma_above_bound:+.1f} sigma). "
        "Both computations are correct; they answer different questions about the instrument."
    )
    options = [
        _option(
            "INCLUDE_FLAGGED",
            "Keep the flagged sub-run; report the above-bound screening result.",
            (
                f"The proposed report uses S = {including.s_value:.4f}, above the classical "
                "bound. The instrument flag must be justified in the write-up. "
                "The original certificate is unchanged."
            ),
        ),
        _option(
            "EXCLUDE_FLAGGED",
            "Drop the flagged sub-run; report the alternative screening result.",
            (
                f"The proposed report uses S = {excluding.s_value:.4f}, consistent with the "
                "classical bound. The exclusion must be pre-registered or justified. "
                "The original certificate is unchanged."
            ),
        ),
        _option(
            "DEFER_PENDING_INSTRUMENT_LOG",
            "Defer until the detector log for the flagged window is reviewed.",
            "Nothing is presented today; the decision is made on instrument evidence instead.",
        ),
    ]
    return question, context, options, None


def _review(assessment: Assessment, outcome: RuleOutcome) -> EscalationDraft:
    question = (
        f"Claim {assessment.claim_id} reproduces numerically but cannot be certified. "
        "Accept it as is?"
    )
    context = f"{outcome.headline} {outcome.finding.detail}".strip()
    options = [
        _option(
            "REQUEST_MISSING_EVIDENCE",
            "Ask the submitter for the missing provenance before the claim is used.",
            "The number stands, but nothing is certified until the record is complete.",
        ),
        _option(
            "ACCEPT_WITH_RECORDED_GAP",
            "Accept the claim with the provenance gap recorded on the certificate.",
            "The certificate states explicitly which checks were not satisfied.",
        ),
    ]
    return question, context, options, "REQUEST_MISSING_EVIDENCE"


def build_escalation(
    assessment: Assessment, outcome: RuleOutcome, *, deadline_note: str = ""
) -> Escalation | None:
    """Return the single decision a human must make, or None if there is none."""
    if outcome.verdict is Verdict.ALLOW:
        return None

    recommended: str | None
    if outcome.verdict is Verdict.HUMAN_DECISION:
        question, context, options, recommended = _human_decision(assessment)
    elif outcome.verdict is Verdict.BLOCK and outcome.rule_id == "R-005":
        question, context, options, recommended = _blocked_by_disagreement(assessment)
    elif outcome.verdict is Verdict.BLOCK and outcome.rule_id == "R-002":
        question, context, options, recommended = _blocked_by_integrity(assessment)
    elif outcome.verdict is Verdict.BLOCK:
        question = f"Claim {assessment.claim_id} was blocked: {outcome.headline}"
        context = outcome.finding.detail or outcome.finding.summary
        options = [
            _option(
                "REQUEST_CORRECTED_SUBMISSION",
                "Return the claim to the submitter for correction.",
                "Nothing is presented until a corrected package arrives.",
            ),
            _option(
                "EXCLUDE_RUN",
                "Exclude this run from the review.",
                "No result is presented for this dataset.",
            ),
        ]
        recommended = "REQUEST_CORRECTED_SUBMISSION"
    elif outcome.rule_id == "R-010":
        question = "How should the reproduced statistic be handled pending statistical review?"
        context = outcome.finding.detail
        options = [
            _option(
                "REQUEST_STATISTICAL_REVIEW",
                "Review finite-sample uncertainty and experimental assumptions.",
                "The numerical result is retained; no physical conclusion is authorized.",
            ),
            _option(
                "REPORT_REPLAY_ONLY",
                "Report only that the supplied number was numerically reproduced.",
                "Keep the review warning and do not describe a certified Bell violation.",
            ),
        ]
        recommended = "REQUEST_STATISTICAL_REVIEW"
    else:
        question, context, options, recommended = _review(assessment, outcome)

    escalation = Escalation(
        escalation_id=f"ESC-{assessment.claim_id}",
        question=question,
        context=context,
        options=tuple(options),
        recommended_option_id=recommended,
        deadline_note=deadline_note,
    )
    assert_escalation_invariants(escalation, outcome)
    return escalation


class EscalationPolicyViolation(AssertionError):
    """Raised when an escalation breaks a product invariant."""


def assert_escalation_invariants(escalation: Escalation, outcome: RuleOutcome) -> None:
    if outcome.verdict is Verdict.HUMAN_DECISION and escalation.recommended_option_id is not None:
        raise EscalationPolicyViolation(
            "a HUMAN_DECISION escalation must not carry a recommendation"
        )
    if len(escalation.options) < 2:
        raise EscalationPolicyViolation("an escalation must offer at least two options")
    ids = [option.option_id for option in escalation.options]
    if len(ids) != len(set(ids)):
        raise EscalationPolicyViolation("escalation options must have unique identifiers")
    if escalation.recommended_option_id is not None and escalation.recommended_option_id not in ids:
        raise EscalationPolicyViolation("recommended option is not one of the offered options")
