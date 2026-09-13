"""Hand-computable counterexamples, independent of the fixture generator math."""

import itertools
import math
from fractions import Fraction

import pytest

from agent.researchops_agent import _build_replay_report, verify_package
from agent.schemas import ClaimState, PhysicalInterpretation, ProvenanceReport, Verdict
from agent.state import Assessment
from evidence.certificate import issue_certificate, verify_signature
from evidence.execution_trace import Tracer
from evidence.verdict_card import build_verdict_card
from policy.escalation import build_escalation
from policy.verdict_rules import apply_rules
from tools.artifact_reader import read_package
from tools.report_generator import render_certificate_markdown, render_verdict_text


def package_for(adversarial, *, positive=1710, negative=290, direction=1):
    package = read_package(adversarial / "case_l_finite_sample_boundary" / "inputs")
    rows = []
    for row in package.counts:
        pair = package.convention.blocks[row.block_id].pair
        sign = package.convention.chsh_combination[pair] * direction
        rows.append(
            row.model_copy(
                update={
                    "n_pp": positive if sign > 0 else negative,
                    "n_pm": negative if sign > 0 else positive,
                    "n_mp": 0,
                    "n_mm": 0,
                }
            )
        )
    package.counts = rows
    package.claim.value = direction * 4 * (positive - negative) / (positive + negative)
    return package


def assess(package):
    # Unit isolation: no claim that these in-memory mutations passed file hashes.
    replay, error = _build_replay_report(package, Tracer())
    assert error is None
    assessment = Assessment(
        package=package, replay=replay, provenance=ProvenanceReport(findings=())
    )
    rule = apply_rules(assessment)
    card = build_verdict_card(assessment, rule, build_escalation(assessment, rule))
    return assessment, card, issue_certificate(assessment, card)


def test_local_fair_products_can_give_empirical_four():
    # Four different, independent trials, one per setting pair. A local model
    # with fresh independent fair outcomes has true correlation zero everywhere.
    products = list(itertools.product((-1, 1), repeat=4))
    sums = [ab - abp + apb + apbp for ab, abp, apb, apbp in products]
    assert Fraction(sums.count(4), len(sums)) == Fraction(1, 16)
    assert Fraction(sum(sums), len(sums)) == 0
    assert max(sums) > 2 * math.sqrt(2)


def test_hand_computed_four_shot_fixture_is_review_not_physics_block(adversarial):
    run = verify_package(adversarial / "case_l_finite_sample_boundary" / "inputs")
    assert run.card.numbers["replayed_S"] == 1 - (-1) + 1 + 1 == 4
    assert run.card.numbers["sigma_S"] == 0
    assert "delta_in_sigma" not in run.card.numbers
    assert "sigma_above_bound" not in run.card.numbers
    assert run.assessment.replay.delta_in_sigma is None
    assert run.card.claim_state is ClaimState.REPRODUCED
    assert run.card.verdict is Verdict.REVIEW
    assert run.card.fired_rule == "R-010"
    assert run.card.physical_interpretation is PhysicalInterpretation.REQUIRES_REVIEW
    assert run.card.escalation.recommended_option_id == "REQUEST_STATISTICAL_REVIEW"
    assert verify_signature(run.certificate)
    assert "REQUIRES_REVIEW" in render_certificate_markdown(run.certificate)
    assert "sigma ratio unavailable" in render_verdict_text(run.card)


@pytest.mark.parametrize("direction", [-1, 1])
def test_finite_estimate_near_quantum_boundary_is_not_rejected(adversarial, direction):
    assessment, card, certificate = assess(package_for(adversarial, direction=direction))
    assert assessment.replay.registered.s_value == pytest.approx(direction * 2.84)
    assert assessment.replay.registered.sigma_s > 0
    assert card.verdict is Verdict.REVIEW
    assert card.claim_state is ClaimState.REPRODUCED
    assert card.physical_interpretation is PhysicalInterpretation.REQUIRES_REVIEW
    assert verify_signature(certificate)


@pytest.mark.parametrize("direction", [-1, 1])
def test_allow_below_quantum_bound_still_does_not_establish_physics(adversarial, direction):
    assessment, card, _ = assess(
        package_for(adversarial, positive=1700, negative=300, direction=direction)
    )
    assert assessment.replay.registered.s_value == pytest.approx(direction * 2.8)
    assert assessment.replay.registered.violates_bound  # Legacy name: a screen only.
    assert card.verdict is Verdict.ALLOW
    assert card.physical_interpretation is PhysicalInterpretation.NOT_ESTABLISHED
    assert "Physical interpretation is not established" in card.headline


@pytest.mark.parametrize(
    "mutation",
    [
        "all_positive",
        "non_unit",
        "classical_bound",
        "quantum_bound",
        "setting",
        "statistic",
        "missing_pair",
    ],
)
def test_definition_checks_block_even_when_numbers_agree(adversarial, mutation):
    package = package_for(adversarial, positive=1200, negative=800)
    if mutation == "all_positive":
        package.convention.chsh_combination = dict.fromkeys(package.convention.chsh_combination, 1)
        package.claim.value = 0.4  # +.2 -.2 +.2 +.2: below either expectation bound.
    elif mutation == "non_unit":
        package.convention.chsh_combination["a_b"] = 2
        package.claim.value = 1.0
    elif mutation == "classical_bound":
        package.convention.classical_bound = 20
    elif mutation == "quantum_bound":
        package.convention.tsirelson_bound = 40
    elif mutation == "setting":
        package.counts[0] = package.counts[0].model_copy(update={"setting_a": "not_registered"})
    elif mutation == "statistic":
        package.claim.statistic = "UNSUPPORTED"
    else:
        del package.convention.chsh_combination["a_b"]
        package.claim.value = 0.6
    assessment, card, _ = assess(package)
    assert assessment.replay.agrees
    assert not assessment.replay.diagnostics.convention_valid
    assert card.fired_rule == "R-004"
    assert card.claim_state is ClaimState.UNVERIFIED
    assert card.physical_interpretation is PhysicalInterpretation.NOT_ASSESSED


def test_definition_failure_outranks_out_of_range_claim(adversarial):
    package = package_for(adversarial)
    package.convention.chsh_combination = dict.fromkeys(package.convention.chsh_combination, 1)
    package.claim.value = 4.2
    _, card, _ = assess(package)
    assert card.fired_rule == "R-004"


def test_zero_plugin_variance_below_quantum_bound_requires_review(adversarial):
    package = package_for(adversarial, positive=1, negative=0)
    for index in (0, 2):
        package.counts[index] = package.counts[index].model_copy(update={"n_pp": 0, "n_pm": 1})
    package.claim.value = 0
    assessment, card, _ = assess(package)
    assert assessment.replay.registered.s_value == 0
    assert not assessment.replay.diagnostics.empirical_above_tsirelson
    assert card.fired_rule == "R-010"
    assert card.verdict is Verdict.REVIEW


def test_zero_uncertainty_mismatch_never_invents_sigma_significance(adversarial):
    package = package_for(adversarial, positive=1, negative=0)
    package.claim.value = 3.5
    _, card, _ = assess(package)
    assert card.fired_rule == "R-005"
    assert "sigma ratio is undefined" in card.findings[-1].detail
    assert "delta_in_sigma" not in card.numbers
    assert "sigma ratio unavailable" in render_verdict_text(card)


def test_missing_definition_diagnostics_fail_closed(adversarial):
    assessment, _, _ = assess(package_for(adversarial, positive=1700, negative=300))
    assessment.replay.diagnostics = None
    assert apply_rules(assessment).rule_id == "R-004"
