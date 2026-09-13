"""Check that the package describes itself honestly.

Provenance failures are cheap to detect and expensive to miss. They run before
any replay, because replaying the wrong dataset produces a confident, wrong
answer.
"""

from __future__ import annotations

from pathlib import Path

from agent.schemas import ExperimentPackage, Finding, ProvenanceReport, Severity
from tools.artifact_reader import RAW_COUNTS, sha256_file

CHECK_MANIFEST_HASHES = "PRV-001"
CHECK_CLAIM_DATASET = "PRV-002"
CHECK_CONVENTION_ID = "PRV-003"
CHECK_CONVENTION_REGISTERED = "PRV-004"
CHECK_ANALYSIS_SCRIPT = "PRV-005"
CHECK_ENVIRONMENT = "PRV-006"


def check_provenance(package: ExperimentPackage) -> ProvenanceReport:
    root = Path(package.root)
    findings: list[Finding] = []

    mismatched: dict[str, dict[str, str]] = {}
    absent: list[str] = []
    for relative, expected in sorted(package.manifest.files.items()):
        path = root / relative
        if not path.exists():
            absent.append(relative)
            continue
        actual = sha256_file(path)
        if actual != expected:
            mismatched[relative] = {"declared": expected, "actual": actual}

    if mismatched or absent:
        findings.append(
            Finding(
                check_id=CHECK_MANIFEST_HASHES,
                severity=Severity.CRITICAL,
                summary="Package contents do not match the manifest.",
                detail=(
                    f"{len(mismatched)} file(s) hash differently than declared; "
                    f"{len(absent)} declared file(s) are missing."
                ),
                evidence={"mismatched": mismatched, "missing": absent},
            )
        )
    else:
        findings.append(
            Finding(
                check_id=CHECK_MANIFEST_HASHES,
                severity=Severity.INFO,
                summary=f"All {len(package.manifest.files)} manifest entries hash as declared.",
            )
        )

    actual_dataset = sha256_file(root / RAW_COUNTS)
    if package.claim.dataset_sha256 != actual_dataset:
        findings.append(
            Finding(
                check_id=CHECK_CLAIM_DATASET,
                severity=Severity.CRITICAL,
                summary="The claim was computed against a different dataset than the one supplied.",
                detail=(
                    f"Claim {package.claim.claim_id} names dataset "
                    f"{package.claim.dataset_id} with sha256 "
                    f"{package.claim.dataset_sha256[:16]}..., but {RAW_COUNTS} in this package "
                    f"hashes to {actual_dataset[:16]}...."
                ),
                evidence={
                    "claimed_dataset_id": package.claim.dataset_id,
                    "claimed_sha256": package.claim.dataset_sha256,
                    "actual_sha256": actual_dataset,
                },
            )
        )
    else:
        findings.append(
            Finding(
                check_id=CHECK_CLAIM_DATASET,
                severity=Severity.INFO,
                summary="The claim names exactly the dataset supplied in this package.",
                evidence={"dataset_sha256": actual_dataset},
            )
        )

    if package.claim.convention_id != package.convention.convention_id:
        findings.append(
            Finding(
                check_id=CHECK_CONVENTION_ID,
                severity=Severity.CRITICAL,
                summary="The claim cites a different analysis convention than the one supplied.",
                evidence={
                    "claimed": package.claim.convention_id,
                    "supplied": package.convention.convention_id,
                },
            )
        )
    else:
        findings.append(
            Finding(
                check_id=CHECK_CONVENTION_ID,
                severity=Severity.INFO,
                summary=(
                    f"Claim and package agree on convention {package.convention.convention_id}."
                ),
            )
        )

    if not package.convention.is_registered:
        findings.append(
            Finding(
                check_id=CHECK_CONVENTION_REGISTERED,
                severity=Severity.WARN,
                summary="The analysis convention is not registered.",
                detail=(
                    f"Convention {package.convention.convention_id} carries no registry entry "
                    "or registration timestamp, so a replay cannot be tied to an agreed standard."
                ),
            )
        )
    else:
        findings.append(
            Finding(
                check_id=CHECK_CONVENTION_REGISTERED,
                severity=Severity.INFO,
                summary=(
                    f"Convention {package.convention.convention_id} registered in "
                    f"{package.convention.registry} on {package.convention.registered_at}."
                ),
            )
        )

    script = package.claim.analysis_script
    if not script or script not in package.manifest.files:
        findings.append(
            Finding(
                check_id=CHECK_ANALYSIS_SCRIPT,
                severity=Severity.WARN,
                summary="The analysis code behind the claim was not submitted.",
                detail=(
                    "Only an independent replay is possible; the submitted analysis path cannot "
                    "be read directly."
                ),
                evidence={"analysis_script": script or ""},
            )
        )
    else:
        findings.append(
            Finding(
                check_id=CHECK_ANALYSIS_SCRIPT,
                severity=Severity.INFO,
                summary=f"Analysis script {script} is present in the package.",
            )
        )

    if not package.manifest.environment:
        findings.append(
            Finding(
                check_id=CHECK_ENVIRONMENT,
                severity=Severity.WARN,
                summary="No environment lock was recorded for the original analysis.",
            )
        )
    else:
        findings.append(
            Finding(
                check_id=CHECK_ENVIRONMENT,
                severity=Severity.INFO,
                summary="Environment lock recorded.",
                evidence=dict(package.manifest.environment),
            )
        )

    return ProvenanceReport(findings=tuple(findings))
