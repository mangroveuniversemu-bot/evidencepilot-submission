"""The verification run, and the Strands agent that narrates it.

Two entry points, deliberately separable:

* :func:`verify_package` is the deterministic pipeline. No network, no model,
  no credentials. It is what the tests exercise and what CI runs.
* :func:`run_model_report` uses the case-bound, stateful Strands investigation
  in poc_narrator. The model requests legal actions and explains their results;
  it cannot change the independent certificate.

Keeping these apart is the point. If the model is unavailable, the verdict is
still computable, and the number in the certificate is identical either way.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agent.schemas import EvidenceCertificate, ExecutionTrace, ReplayReport, VerdictCard
from agent.state import Assessment
from evidence.certificate import issue_certificate
from evidence.execution_trace import Tracer
from evidence.verdict_card import build_verdict_card
from policy.escalation import build_escalation
from policy.verdict_rules import apply_rules
from tools.artifact_reader import hash_package, read_package
from tools.chsh_diagnostics import diagnose_chsh
from tools.chsh_replay import ReplayError, compute_chsh, has_flagged_subruns
from tools.provenance_checker import check_provenance
from tools.root_cause import _tolerance, find_root_cause

AGREEMENT_SIGMA = 3.0


class VerificationRun(BaseModel):
    """Everything one verification produced, in one object."""

    assessment: Assessment
    card: VerdictCard
    certificate: EvidenceCertificate
    trace: ExecutionTrace


def _build_replay_report(package, tracer: Tracer) -> tuple[ReplayReport | None, str | None]:
    try:
        args = {"convention": package.convention.convention_id}
        with tracer.step("chsh_replay.compute_chsh", args) as step:
            registered = compute_chsh(package.counts, package.convention)
            step.result = {"s": registered.s_value, "sigma": registered.sigma_s}
    except ReplayError as exc:
        return None, str(exc)

    alternative = None
    if has_flagged_subruns(package.counts):
        primary_includes = package.convention.subrun_inclusion != "unflagged_only"
        try:
            with tracer.step(
                "chsh_replay.compute_chsh", {"include_flagged": not primary_includes}
            ) as step:
                alternative = compute_chsh(
                    package.counts, package.convention, include_flagged=not primary_includes
                )
                step.result = {"s": alternative.s_value, "sigma": alternative.sigma_s}
        except ReplayError:
            alternative = None

    claimed = package.claim.value
    delta = claimed - registered.s_value
    sigma = registered.sigma_s
    tolerance = max(AGREEMENT_SIGMA * sigma, _tolerance(claimed))
    with tracer.step("chsh_diagnostics.diagnose_chsh", {}) as step:
        diagnostics = diagnose_chsh(package, registered)
        step.result = diagnostics.model_dump(mode="json")
    return (
        ReplayReport(
            registered=registered,
            robustness_alternative=alternative,
            claimed_value=claimed,
            delta_s=delta,
            delta_in_sigma=delta / sigma if sigma > 0 else None,
            agrees=abs(delta) <= tolerance,
            tolerance=tolerance,
            diagnostics=diagnostics,
        ),
        None,
    )


def verify_package(root: str | Path, *, deadline_note: str = "") -> VerificationRun:
    """Run the full deterministic verification of one experiment package."""
    tracer = Tracer()

    with tracer.step("artifact_reader.read_package", {"root": str(root)}) as step:
        package = read_package(root)
        step.result = package.manifest.package_id

    provenance_args = {"package": package.manifest.package_id}
    with tracer.step("provenance_checker.check_provenance", provenance_args) as step:
        provenance = check_provenance(package)
        step.result = [f.check_id + ":" + f.severity.value for f in provenance.findings]

    replay: ReplayReport | None = None
    replay_error: str | None = None
    root_cause = None

    if provenance.critical:
        # Replaying against inputs that do not match the claim produces a
        # confident answer to the wrong question. Stop here instead.
        tracer.record(
            "chsh_replay.compute_chsh",
            {"skipped": True},
            "skipped",
            "input integrity failed",
        )
    else:
        replay, replay_error = _build_replay_report(package, tracer)
        if replay is not None and not replay.agrees:
            root_args = {"claim": package.claim.claim_id}
            with tracer.step("root_cause.find_root_cause", root_args) as step:
                root_cause = find_root_cause(package.counts, package.convention, package.claim)
                step.result = list(root_cause.full_matches)

    assessment = Assessment(
        package=package,
        provenance=provenance,
        replay=replay,
        root_cause=root_cause,
        replay_error=replay_error,
    )

    with tracer.step("verdict_rules.apply_rules", {"claim": assessment.claim_id}) as step:
        outcome = apply_rules(assessment)
        step.result = {"rule": outcome.rule_id, "verdict": outcome.verdict.value}

    with tracer.step("escalation.build_escalation", {"rule": outcome.rule_id}) as step:
        escalation = build_escalation(assessment, outcome, deadline_note=deadline_note)
        step.result = escalation.escalation_id if escalation else None

    card = build_verdict_card(assessment, outcome, escalation)
    trace = tracer.build()
    certificate = issue_certificate(
        assessment, card, trace=trace, input_hashes=hash_package(package.root)
    )
    return VerificationRun(assessment=assessment, card=card, certificate=certificate, trace=trace)


# ---------------------------------------------------------------------------
# Strands wiring
# ---------------------------------------------------------------------------


def _summarise(run: VerificationRun) -> dict[str, Any]:
    card = run.card
    return {
        "verdict": card.verdict.value,
        "claim_state": card.claim_state.value,
        "evidence_class": card.evidence_class.value,
        "physical_interpretation": card.physical_interpretation.value,
        "fired_rule": card.fired_rule,
        "headline": card.headline,
        "root_cause": card.root_cause,
        "numbers": card.numbers,
        "escalation": card.escalation.model_dump(mode="json") if card.escalation else None,
        "certificate_id": run.certificate.certificate_id,
        "signature": run.certificate.signature,
    }


# Legacy deterministic projections used by offline compatibility tests. Live
# model tools are zero-argument, state-gated tools in agent/poc_narrator.py;
# tests/integration/test_investigation.py exercises their real data surface.

TOOL_PROJECTIONS = (
    "read_experiment_package",
    "check_provenance",
    "replay_chsh",
    "search_root_cause",
    "issue_verdict",
)


def read_experiment_package(package_path: str) -> dict:
    """Parse a submitted experiment package and report what it contains."""
    package = read_package(package_path)
    return {
        "package_id": package.manifest.package_id,
        "experiment_id": package.manifest.experiment_id,
        "claim_id": package.claim.claim_id,
        "claimed_statistic": package.claim.statistic,
        "claimed_value": package.claim.value,
        "convention_id": package.convention.convention_id,
        "acquisition_rows": len(package.counts),
        "flagged_subruns": [f"{r.block_id}/{r.subrun_id}" for r in package.counts if r.flags],
    }


def check_provenance_projection(package_path: str) -> dict:
    """Verify that the package matches its manifest and its claim."""
    report = check_provenance(read_package(package_path))
    return {
        "complete": report.complete,
        "findings": [f.model_dump(mode="json") for f in report.findings],
    }


def replay_chsh(package_path: str) -> dict:
    """Recompute the CHSH statistic from raw counts under the registered convention."""
    package = read_package(package_path)
    result = compute_chsh(package.counts, package.convention)
    return {
        "s_value": result.s_value,
        "sigma_s": result.sigma_s,
        "sigma_above_bound": result.sigma_above_bound,
        "violates_classical_bound": result.violates_bound,
        "per_pair_correlation": result.per_pair(),
        "claimed_value": package.claim.value,
    }


def search_root_cause(package_path: str) -> dict:
    """Find which single deviation from the registered convention reproduces the claim."""
    package = read_package(package_path)
    report = find_root_cause(package.counts, package.convention, package.claim)
    return {
        "conclusion": report.conclusion,
        "value_matches": list(report.value_matches),
        "full_matches": list(report.full_matches),
        "identified": report.identified.model_dump(mode="json") if report.identified else None,
    }


def issue_verdict(package_path: str) -> dict:
    """Apply the deterministic rule table and issue the verdict and certificate."""
    return _summarise(verify_package(package_path))


def model_visible_surface(package_path: str) -> dict[str, dict]:
    """Legacy projection fixture; this does not run or evaluate a live model."""
    return {
        "read_experiment_package": read_experiment_package(package_path),
        "check_provenance": check_provenance_projection(package_path),
        "replay_chsh": replay_chsh(package_path),
        "search_root_cause": search_root_cause(package_path),
        "issue_verdict": issue_verdict(package_path),
    }


def run_model_report(
    package_path: str,
    *,
    model_id: str | None = None,
    region_name: str | None = None,
    deadline_note: str = "",
) -> dict:
    """Trusted-operator CLI adapter to the same bounded investigation as the POC.

    The operator selects the package. Never expose this path-taking adapter as
    a model tool or public endpoint; the hosted API accepts bundled case IDs.
    """
    from agent.poc_narrator import narrate_case
    from evidence.certificate import verify_signature

    root = Path(package_path).resolve()
    run = verify_package(root, deadline_note=deadline_note)
    certificate = json.loads(run.certificate.model_dump_json())
    advisory = narrate_case(
        root, run.model_copy(deep=True), model_id=model_id, region_name=region_name
    )
    return {
        "certificate": certificate,
        "certificate_integrity_valid": verify_signature(run.certificate),
        "integrity_note": "SHA-256 integrity checksum; not an authenticated signature.",
        "advisory": advisory,
    }


def run_with_model(
    package_path: str, *, model_id: str | None = None, region_name: str | None = None
) -> str:
    """Compatibility prose adapter; incomplete investigations are not success."""
    report = run_model_report(package_path, model_id=model_id, region_name=region_name)
    if report["advisory"]["status"] != "complete":
        raise RuntimeError("investigation_not_complete")
    return report["advisory"]["text"]
