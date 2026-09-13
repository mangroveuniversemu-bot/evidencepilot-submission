"""Assemble the one-screen answer a person actually reads."""

from __future__ import annotations

from agent.schemas import Escalation, VerdictCard
from agent.state import Assessment
from policy.verdict_rules import RuleOutcome, evidence_class_for, physical_interpretation_for


def build_verdict_card(
    assessment: Assessment, outcome: RuleOutcome, escalation: Escalation | None
) -> VerdictCard:
    numbers: dict[str, float] = {}
    root_cause: str | None = None

    if assessment.replay is not None:
        replay = assessment.replay
        numbers.update(
            {
                "claimed_S": replay.claimed_value,
                "replayed_S": replay.registered.s_value,
                "sigma_S": replay.registered.sigma_s,
                "delta_S": replay.delta_s,
                "classical_bound": replay.registered.classical_bound,
            }
        )
        if replay.delta_in_sigma is not None:
            numbers["delta_in_sigma"] = replay.delta_in_sigma
        if replay.registered.sigma_s > 0:
            numbers["sigma_above_bound"] = replay.registered.sigma_above_bound
        for correlation in replay.registered.correlations:
            numbers[f"E({correlation.pair})"] = correlation.e_value
        if replay.robustness_alternative is not None:
            numbers["replayed_S_excluding_flagged"] = replay.robustness_alternative.s_value

    if assessment.root_cause is not None and assessment.root_cause.identified is not None:
        root_cause = assessment.root_cause.identified.description

    # The firing rule usually restates the provenance check that triggered it;
    # showing it twice adds noise, so the rule finding wins on ties.
    seen = {outcome.finding.summary}
    findings = tuple(f for f in assessment.provenance.findings if f.summary not in seen) + (
        outcome.finding,
    )

    return VerdictCard(
        verdict=outcome.verdict,
        claim_state=outcome.claim_state,
        evidence_class=evidence_class_for(assessment),
        physical_interpretation=physical_interpretation_for(assessment),
        claim_id=assessment.claim_id,
        headline=outcome.headline,
        root_cause=root_cause,
        numbers={key: round(value, 6) for key, value in numbers.items()},
        findings=findings,
        fired_rule=outcome.rule_id,
        escalation=escalation,
    )
