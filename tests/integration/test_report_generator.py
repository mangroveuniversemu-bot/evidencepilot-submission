"""Rendering: the numbers on screen must be the numbers in the certificate."""

from __future__ import annotations

from agent.researchops_agent import verify_package
from tools.report_generator import (
    render_certificate_markdown,
    render_queue_summary,
    render_verdict_text,
)


def test_verdict_text_shows_both_numbers_and_the_root_cause(maya_run):
    text = render_verdict_text(maya_run.card)
    assert "2.6100" in text and "1.9625" in text
    assert "ROOT CAUSE" in text
    assert "BLK-02" in text
    assert "ONE DECISION REQUIRED" in text


def test_allow_verdict_asks_for_nothing(repo_root):
    run = verify_package(repo_root / "examples/adversarial/case_e_clean_pass/inputs")
    text = render_verdict_text(run.card)
    assert "NO DECISION REQUIRED" in text
    assert "ONE DECISION REQUIRED" not in text


def test_human_decision_offers_no_recommendation(repo_root):
    run = verify_package(repo_root / "examples/adversarial/case_d_human_decision/inputs")
    text = render_verdict_text(run.card)
    assert "This one is yours to make" in text
    assert "Suggested:" not in text


def test_certificate_markdown_carries_limitations_and_signature(maya_run):
    markdown = render_certificate_markdown(maya_run.certificate)
    assert maya_run.certificate.signature in markdown
    assert "## Limitations" in markdown
    assert "## Execution trace" in markdown
    assert "not a finding of error by the submitter" in markdown


def test_queue_summary_counts_what_needs_a_human(repo_root):
    paths = [
        "examples/adversarial/case_e_clean_pass/inputs",
        "examples/adversarial/case_c_missing_evidence/inputs",
        "examples/adversarial/case_d_human_decision/inputs",
        "examples/maya_case/inputs",
    ]
    cards = [verify_package(repo_root / p).card for p in paths]
    summary = render_queue_summary(cards)
    assert "1 verified" in summary
    assert "3 require a decision." in summary
