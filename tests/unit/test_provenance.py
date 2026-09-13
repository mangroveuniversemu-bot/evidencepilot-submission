"""Provenance checks, one failure at a time."""

from __future__ import annotations

from agent.schemas import Severity
from tools.artifact_reader import read_package
from tools.provenance_checker import (
    CHECK_ANALYSIS_SCRIPT,
    CHECK_CLAIM_DATASET,
    CHECK_CONVENTION_ID,
    CHECK_CONVENTION_REGISTERED,
    CHECK_ENVIRONMENT,
    CHECK_MANIFEST_HASHES,
    check_provenance,
)


def _by_id(report, check_id):
    return next(f for f in report.findings if f.check_id == check_id)


def test_clean_package_passes_every_check(adversarial):
    report = check_provenance(read_package(adversarial / "case_e_clean_pass" / "inputs"))
    assert report.complete
    assert all(f.severity is Severity.INFO for f in report.findings)


def test_stale_dataset_is_critical(adversarial):
    report = check_provenance(read_package(adversarial / "case_a_stale_artifact" / "inputs"))
    finding = _by_id(report, CHECK_CLAIM_DATASET)
    assert finding.severity is Severity.CRITICAL
    assert finding.evidence["claimed_sha256"] != finding.evidence["actual_sha256"]
    # The manifest itself is intact; only the claim points elsewhere.
    assert _by_id(report, CHECK_MANIFEST_HASHES).severity is Severity.INFO


def test_unregistered_convention_warns(adversarial):
    report = check_provenance(read_package(adversarial / "case_c_missing_evidence" / "inputs"))
    assert _by_id(report, CHECK_CONVENTION_REGISTERED).severity is Severity.WARN
    assert _by_id(report, CHECK_CONVENTION_ID).severity is Severity.INFO
    assert not report.complete


def test_missing_analysis_script_and_environment_warn(maya_inputs):
    report = check_provenance(read_package(maya_inputs))
    assert _by_id(report, CHECK_ANALYSIS_SCRIPT).severity is Severity.WARN
    assert _by_id(report, CHECK_ENVIRONMENT).severity is Severity.WARN


def test_tampered_file_is_detected(tmp_path, adversarial):
    import shutil

    source = adversarial / "case_e_clean_pass" / "inputs"
    target = tmp_path / "inputs"
    shutil.copytree(source, target)
    counts = target / "raw_counts.csv"
    counts.write_text(counts.read_text().replace("8110", "8111"), encoding="utf-8")

    report = check_provenance(read_package(target))
    assert _by_id(report, CHECK_MANIFEST_HASHES).severity is Severity.CRITICAL
