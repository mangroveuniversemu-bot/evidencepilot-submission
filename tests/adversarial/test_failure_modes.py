"""One test per failure class the agent is expected to survive."""

from __future__ import annotations

import shutil

import pytest
from pydantic import ValidationError

from agent.researchops_agent import verify_package
from agent.schemas import Verdict


def test_a_stale_artifact_blocks_without_replaying(repo_root):
    run = verify_package(repo_root / "examples/adversarial/case_a_stale_artifact/inputs")
    assert run.card.verdict is Verdict.BLOCK
    assert run.assessment.replay is None


def test_a_disagreement_blocks_and_names_the_step(repo_root):
    run = verify_package(repo_root / "examples/maya_case/inputs")
    assert run.card.verdict is Verdict.BLOCK
    assert run.card.root_cause is not None
    assert "BLK-02" in run.card.root_cause


def test_incomplete_evidence_is_review_not_block(repo_root):
    run = verify_package(repo_root / "examples/adversarial/case_c_missing_evidence/inputs")
    assert run.card.verdict is Verdict.REVIEW
    # The arithmetic was fine; only the record was not.
    assert run.assessment.replay.agrees


def test_a_consequential_choice_goes_to_a_human(repo_root):
    run = verify_package(repo_root / "examples/adversarial/case_d_human_decision/inputs")
    assert run.card.verdict is Verdict.HUMAN_DECISION
    including = run.assessment.replay.registered
    excluding = run.assessment.replay.robustness_alternative
    assert including.violates_bound != excluding.violates_bound


def test_a_clean_package_is_allowed(repo_root):
    run = verify_package(repo_root / "examples/adversarial/case_e_clean_pass/inputs")
    assert run.card.verdict is Verdict.ALLOW


def test_a_truncated_package_fails_loudly(tmp_path, repo_root):
    source = repo_root / "examples/adversarial/case_e_clean_pass/inputs"
    target = tmp_path / "inputs"
    shutil.copytree(source, target)
    (target / "convention.json").unlink()
    with pytest.raises(FileNotFoundError, match="convention.json"):
        verify_package(target)


def test_a_corrupt_counts_file_fails_loudly(tmp_path, repo_root):
    source = repo_root / "examples/adversarial/case_e_clean_pass/inputs"
    target = tmp_path / "inputs"
    shutil.copytree(source, target)
    counts = target / "raw_counts.csv"
    counts.write_text(counts.read_text().replace("8110", "-1"), encoding="utf-8")
    with pytest.raises(ValidationError):
        verify_package(target)


def test_an_empty_counts_file_fails_loudly(tmp_path, repo_root):
    source = repo_root / "examples/adversarial/case_e_clean_pass/inputs"
    target = tmp_path / "inputs"
    shutil.copytree(source, target)
    header = (target / "raw_counts.csv").read_text().splitlines()[0]
    (target / "raw_counts.csv").write_text(header + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no acquisition rows"):
        verify_package(target)
