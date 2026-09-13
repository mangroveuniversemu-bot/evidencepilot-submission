"""Restricted synthetic-case API shared by local and AgentCore deployments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError

from agent.researchops_agent import verify_package
from evidence.certificate import verify_signature

CaseId = Literal["maya", "clean", "missing_evidence", "human_decision", "stale", "injection"]
CASES: dict[str, str] = {
    "maya": "maya_case",
    "clean": "adversarial/case_e_clean_pass",
    "missing_evidence": "adversarial/case_c_missing_evidence",
    "human_decision": "adversarial/case_d_human_decision",
    "stale": "adversarial/case_a_stale_artifact",
    "injection": "adversarial/case_g_prompt_injection",
}
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class PocRequest(BaseModel):
    """Clients select a bundled case; they cannot supply paths or model settings."""

    model_config = ConfigDict(extra="forbid")
    case: CaseId = "maya"
    narrate: StrictBool = False


def handle_request(payload: object) -> dict:
    """Return an independently computed certificate, with optional advisory prose."""
    try:
        request = PocRequest.model_validate(payload)
    except ValidationError:
        return {"ok": False, "error": "invalid_request", "allowed_cases": sorted(CASES)}

    root = EXAMPLES / CASES[request.case] / "inputs"
    run = verify_package(root)
    # Freeze the response before handing a separate run to the advisory layer.
    certificate = json.loads(run.certificate.model_dump_json())
    advisory: dict = {"status": "not_requested", "authority": "advisory", "text": None}
    if request.narrate:
        from agent.poc_narrator import narrate_case

        advisory = narrate_case(root, run.model_copy(deep=True))

    return {
        "ok": True,
        "case": request.case,
        "data_origin": "bundled_synthetic_fixture",
        "certificate": certificate,
        "certificate_integrity_valid": verify_signature(run.certificate),
        "integrity_note": (
            "SHA-256 integrity checksum; not a keyed or identity-authenticated signature."
        ),
        "advisory": advisory,
    }
