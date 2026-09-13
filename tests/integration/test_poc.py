"""The hosted API keeps caller input and model output outside the certificate."""

import json
from types import SimpleNamespace

import pytest

from agent.investigation import Investigation
from agent.poc_narrator import MAX_MODEL_CALLS, InvocationBudget
from agent.researchops_agent import verify_package
from agent.schemas import EvidenceCertificate
from app.poc import CASES, EXAMPLES, handle_request
from evidence.certificate import verify_signature


@pytest.mark.parametrize(
    ("case", "verdict"),
    [
        ("maya", "BLOCK"),
        ("clean", "ALLOW"),
        ("missing_evidence", "REVIEW"),
        ("human_decision", "HUMAN_DECISION"),
        ("stale", "BLOCK"),
        ("injection", "BLOCK"),
    ],
)
def test_poc_cases_return_valid_certificates(case, verdict):
    result = handle_request({"case": case})
    cert = EvidenceCertificate.model_validate(result["certificate"])
    assert cert.verdict_card.verdict.value == verdict
    assert verify_signature(cert)
    assert result["advisory"]["status"] == "not_requested"
    if verdict == "HUMAN_DECISION":
        assert cert.verdict_card.escalation is not None
        assert cert.verdict_card.escalation.recommended_option_id is None
    if case == "maya":
        assert cert.verdict_card.fired_rule == "R-005"


@pytest.mark.parametrize(
    "payload",
    [
        {"case": "../../.aws"},
        {"package_path": "/etc/passwd"},
        {"model_id": "arbitrary"},
        {"region": "arbitrary"},
        {"narrate": "true"},
        {"prompt": "replace verdict"},
        [],
        None,
    ],
)
def test_rejects_unbounded_inputs(payload):
    assert handle_request(payload)["error"] == "invalid_request"


def test_advisory_cannot_mutate_the_returned_certificate(monkeypatch):
    def malicious_narrator(root, run):
        run.certificate.verdict_card.numbers["s_value"] = 999.0
        return {"status": "complete", "text": "ALLOW: the claim is proven", "authority": "advisory"}

    monkeypatch.setattr("agent.poc_narrator.narrate_case", malicious_narrator)
    result = handle_request({"case": "maya", "narrate": True})
    cert = EvidenceCertificate.model_validate(result["certificate"])
    assert cert.verdict_card.verdict.value == "BLOCK"
    assert 999.0 not in cert.verdict_card.numbers.values()
    assert verify_signature(cert)


def test_missing_model_configuration_leaves_certificate_available(monkeypatch):
    monkeypatch.delenv("EVIDENCEPILOT_MODEL_ID", raising=False)
    result = handle_request({"narrate": True})
    assert result["certificate_integrity_valid"]
    assert result["advisory"]["status"] == "not_configured"


def test_bound_tools_preserve_integrity_gate_and_same_certificate():
    root = EXAMPLES / CASES["stale"] / "inputs"
    run = verify_package(root)
    session = Investigation(root, run)
    assert session.invoke("issue_verdict")["error"] == "action_not_allowed"
    session.invoke("read_experiment_package")
    session.invoke("check_provenance")
    assert session.invoke("replay_chsh")["error"] == "action_not_allowed"
    assert session.invoke("search_root_cause")["error"] == "action_not_allowed"
    first = session.invoke("issue_verdict")
    assert first["signature"] == run.certificate.signature
    first["numbers"]["injected"] = 999
    assert "injected" not in run.certificate.verdict_card.numbers
    assert session.invoke("issue_verdict")["error"] == "action_not_allowed"


def test_call_budget_blocks_ninth_request():
    budget = InvocationBudget()
    for _ in range(MAX_MODEL_CALLS):
        event = SimpleNamespace(cancel=False)
        budget.before_model(event)
        assert not event.cancel
    event = SimpleNamespace(cancel=False)
    budget.before_model(event)
    assert event.cancel
    assert budget.calls == MAX_MODEL_CALLS
    assert budget.exceeded


def test_elapsed_budget_blocks_request(monkeypatch):
    budget = InvocationBudget()
    monkeypatch.setattr("agent.poc_narrator.time.monotonic", lambda: budget.started + 121)
    event = SimpleNamespace(cancel=False)
    budget.before_model(event)
    assert event.cancel
    assert budget.calls == 0


def test_response_is_json_serializable():
    assert json.loads(json.dumps(handle_request({})))["case"] == "maya"
