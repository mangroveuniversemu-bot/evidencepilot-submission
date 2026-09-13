"""State-machine, real-tool, and adversarial tests; no model or AWS required."""

import json
import sys
from types import SimpleNamespace

import pytest

from agent.investigation import MAX_TOOL_ATTEMPTS, Investigation
from agent.poc_narrator import narrate_case
from agent.researchops_agent import verify_package
from app.poc import CASES, EXAMPLES
from evidence.certificate import verify_signature
from scripts.build_examples import INJECTION


def setup(case="maya"):
    root = EXAMPLES / CASES[case] / "inputs"
    baseline = verify_package(root)
    return root, baseline, Investigation(root, baseline)


def finish(session):
    outputs = []
    while session.snapshot()["allowed_actions"]:
        outputs.append(session.invoke(session.snapshot()["allowed_actions"][0]))
        assert len(outputs) <= 5
    return outputs


@pytest.mark.parametrize("case", CASES)
def test_all_cases_follow_real_conditional_paths(case):
    _, baseline, session = setup(case)
    original = baseline.certificate.model_dump_json()
    outputs = finish(session)
    assert session.complete
    assert outputs[-1]["verdict"] == baseline.card.verdict.value
    assert outputs[-1]["signature"] == baseline.certificate.signature
    assert baseline.certificate.model_dump_json() == original
    assert verify_signature(baseline.certificate)
    actions = [entry["action"] for entry in session.report()["agent_trace"]]
    if case == "stale":
        assert actions == ["read_experiment_package", "check_provenance", "issue_verdict"]
    elif case in {"maya", "injection"}:
        assert actions[-2] == "search_root_cause"
    else:
        assert "search_root_cause" not in actions
    if case == "human_decision":
        assert outputs[-1]["escalation"]["recommended_option_id"] is None
        assert outputs[-1]["human_attention_required"] is True
        assert outputs[-1]["human_decision_recorded"] is False


def test_direct_final_answer_is_rejected_without_leaking_verdict():
    _, _, session = setup()
    result = session.invoke("issue_verdict")
    assert result["error"] == "action_not_allowed"
    assert "verdict" not in result
    assert "numbers" not in result
    assert session.complete is False
    assert session.report()["agent_trace"][0]["outcome"] == "rejected"


@pytest.mark.parametrize(
    "fixture",
    [
        "case_h_unphysical_claim",
        "case_i_unphysical_convention",
        "case_j_incomplete_counts",
        "case_k_missing_environment",
        "case_l_finite_sample_boundary",
        "case_m_algebraic_claim",
    ],
)
def test_additional_policy_branches_are_reproduced(fixture):
    root = EXAMPLES / "adversarial" / fixture / "inputs"
    baseline = verify_package(root)
    session = Investigation(root, baseline)
    result = finish(session)[-1]
    assert session.complete
    assert result["fired_rule"] == baseline.card.fired_rule
    assert result["verdict"] == baseline.card.verdict.value
    if fixture == "case_j_incomplete_counts":
        assert baseline.assessment.replay_error
        assert "search_root_cause" not in [r["action"] for r in session.report()["agent_trace"]]


def test_changed_inputs_during_a_tool_are_not_disclosed(monkeypatch):
    _, baseline, session = setup()
    hashes = iter([baseline.certificate.input_hashes, {"changed": "yes"}])
    monkeypatch.setattr("agent.investigation.hash_package", lambda root: next(hashes))
    result = session.invoke("read_experiment_package")
    assert result["state"] == "invalidated"
    assert "claimed_value" not in result
    assert session.invoke("check_provenance")["error"] == "action_not_allowed"


def test_rederived_card_must_match_independent_baseline():
    root, baseline, _ = setup("clean")
    baseline.card.headline = "A mismatched result must never be released"
    session = Investigation(root, baseline)
    result = finish(session)[-1]
    assert result["error"] == "BaselineMismatchError"
    assert result["state"] == "failed"
    assert "signature" not in result
    assert not session.complete


def test_model_budget_cancels_after_investigation_failure(monkeypatch):
    from agent.poc_narrator import InvocationBudget

    _, _, session = setup()
    monkeypatch.setattr("agent.investigation.hash_package", lambda root: {})
    session.invoke("read_experiment_package")
    budget = InvocationBudget(session)
    event = SimpleNamespace(cancel=False)
    budget.before_model(event)
    assert event.cancel
    assert budget.calls == 0


def test_malformed_sequence_does_not_advance_state():
    _, _, session = setup("clean")
    assert session.invoke("check_provenance")["state"] == "new"
    session.invoke("read_experiment_package")
    assert session.invoke("read_experiment_package")["state"] == "package_read"
    assert session.invoke("search_root_cause")["state"] == "package_read"
    assert session.invoke("private untrusted text")["state"] == "package_read"
    assert session.report()["agent_trace"][-1]["action"] == "unknown_tool"
    assert "private untrusted text" not in json.dumps(session.report())
    assert finish(session)[-1]["investigation_complete"]


def test_replay_is_an_actual_computation(monkeypatch):
    _, _, session = setup("clean")
    import agent.researchops_agent as pipeline

    actual = pipeline.compute_chsh
    calls = []

    def spy(*args, **kwargs):
        calls.append(True)
        return actual(*args, **kwargs)

    monkeypatch.setattr(pipeline, "compute_chsh", spy)
    finish(session)
    assert calls


def test_failures_are_recorded_without_error_messages(monkeypatch):
    _, _, session = setup()

    def fail(*args):
        raise OSError("private path or credential must never be logged")

    monkeypatch.setattr("agent.investigation.read_package", fail)
    result = session.invoke("read_experiment_package")
    assert result["error"] == "OSError"
    assert result["state"] == "failed"
    report = session.report()
    assert report["agent_trace"][0]["outcome"] == "error"
    assert "private path" not in json.dumps(report)
    assert session.complete is False


def test_changed_inputs_invalidate_even_if_tools_previously_succeeded(monkeypatch):
    _, _, session = setup()
    session.invoke("read_experiment_package")
    monkeypatch.setattr("agent.investigation.hash_package", lambda root: {"changed": "yes"})
    result = session.invoke("check_provenance")
    assert result["state"] == "invalidated"
    assert result["error"] == "InputsChangedError"
    assert session.complete is False


def test_tool_outputs_cannot_mutate_internal_state():
    _, _, session = setup("clean")
    result = session.invoke("read_experiment_package")
    result["claimed_value"] = 999
    result["allowed_actions"][:] = ["issue_verdict"]
    result["state"] = "complete"
    assert session.snapshot()["allowed_actions"] == ["check_provenance"]
    outputs = finish(session)
    assert 999 not in outputs[-1]["numbers"].values()
    report = session.report()
    report["agent_trace"].clear()
    assert session.report()["agent_trace"]


def test_budget_is_bounded_and_cannot_be_recovered_by_a_late_valid_action():
    _, _, session = setup()
    for _ in range(MAX_TOOL_ATTEMPTS + 5):
        session.invoke("issue_verdict")
    assert session.snapshot()["state"] == "budget_exceeded"
    assert len(session.report()["agent_trace"]) == MAX_TOOL_ATTEMPTS + 1
    assert session.invoke("read_experiment_package")["error"] == "tool_budget"


def test_injection_reaches_actual_tool_surface_but_not_authorization():
    _, baseline, session = setup("injection")
    read = session.invoke("read_experiment_package")
    assert INJECTION in json.dumps(read)
    assert session.invoke("issue_verdict")["error"] == "action_not_allowed"
    result = finish(session)[-1]
    assert result["verdict"] == "BLOCK"
    assert result["numbers"] == baseline.card.numbers
    assert verify_signature(baseline.certificate)


def test_live_trace_is_separate_from_baseline_trace():
    _, baseline, session = setup()
    original = baseline.trace.model_dump_json()
    session.invoke("issue_verdict")
    finish(session)
    report = session.report()
    assert baseline.trace.model_dump_json() == original
    assert report["verification_trace"]["trace_id"] != baseline.trace.trace_id
    assert report["agent_trace"][0]["outcome"] == "rejected"
    assert all(
        "state_before" in item and "observation_digest" in item for item in report["agent_trace"]
    )


def mock_sdk(monkeypatch, actions):
    """Scripted SDK stand-in tests protocol behavior, not model intelligence."""

    class FakeAgent:
        def __init__(self, **kwargs):
            self.tools = {tool.__name__: tool for tool in kwargs["tools"]}

        def __call__(self, prompt):
            for action in actions:
                self.tools[action]()
            return SimpleNamespace(
                message={"content": [{"text": "An advisory explanation."}]},
                stop_reason="end_turn",
                metrics=SimpleNamespace(accumulated_usage={}),
            )

    monkeypatch.setitem(
        sys.modules, "strands", SimpleNamespace(Agent=FakeAgent, tool=lambda **kw: lambda fn: fn)
    )
    monkeypatch.setitem(
        sys.modules, "strands.models", SimpleNamespace(BedrockModel=lambda **kw: None)
    )
    monkeypatch.setitem(sys.modules, "botocore.config", SimpleNamespace(Config=lambda **kw: None))


@pytest.mark.parametrize("complete", [False, True])
def test_narrator_requires_completed_investigation_not_just_prose(monkeypatch, complete):
    root, baseline, _ = setup("clean")
    actions = (
        ["read_experiment_package", "check_provenance", "replay_chsh", "issue_verdict"]
        if complete
        else ["issue_verdict"]
    )
    mock_sdk(monkeypatch, actions)
    result = narrate_case(root, baseline, model_id="mock-not-live")
    assert result["status"] == ("complete" if complete else "incomplete")
    assert result["investigation"]["investigation_complete"] is complete
    assert result["prose_checked"] is False
    assert result["run_metadata"]["baseline_checksum"] == baseline.certificate.signature
    assert result["run_metadata"]["limits"]["observation_bytes_per_tool"] == 16 * 1024


@pytest.mark.parametrize("complete", [False, True])
def test_cli_uses_same_bounded_protocol_and_structured_exit(monkeypatch, capsys, complete):
    from app.main import main

    root, _, _ = setup("clean")
    actions = (
        ["read_experiment_package", "check_provenance", "replay_chsh", "issue_verdict"]
        if complete
        else ["issue_verdict"]
    )
    mock_sdk(monkeypatch, actions)
    code = main(["agent", str(root), "--model-id", "mock-not-live", "--json"])
    assert code == (0 if complete else 2)
    report = json.loads(capsys.readouterr().out)
    assert report["certificate_integrity_valid"]
    assert report["advisory"]["investigation"]["investigation_complete"] is complete


def test_cli_without_model_configuration_is_offline_and_not_complete(monkeypatch, capsys):
    from app.main import main

    root, _, _ = setup("clean")
    monkeypatch.delenv("EVIDENCEPILOT_MODEL_ID", raising=False)
    assert main(["agent", str(root), "--json"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["certificate_integrity_valid"]
    assert report["advisory"]["status"] == "not_configured"
    assert report["advisory"]["run_metadata"]["model"]["id"] is None


def test_oversized_first_observation_is_not_returned_or_marked_complete(monkeypatch):
    _, baseline, session = setup("clean")
    original = baseline.certificate.model_dump_json()
    package = baseline.assessment.package.model_copy(deep=True)
    package.manifest.package_id = "OVERSIZED-MARKER" * 2000
    monkeypatch.setattr("agent.investigation.read_package", lambda root: package)
    output = session.invoke("read_experiment_package")
    assert output["state"] == "budget_exceeded"
    assert output["error"] == "ObservationLimitError"
    assert "OVERSIZED-MARKER" not in json.dumps(output)
    assert "claimed_value" not in output
    assert session.report()["accepted_observation_bytes"] == 0
    assert session.invoke("check_provenance")["error"] == "action_not_allowed"
    assert not session.complete
    assert baseline.certificate.model_dump_json() == original
    assert verify_signature(baseline.certificate)


def test_oversized_final_observation_cannot_report_completion(monkeypatch):
    _, baseline, session = setup("clean")
    for action in ("read_experiment_package", "check_provenance", "replay_chsh"):
        session.invoke(action)
    accepted = session.report()["accepted_observation_bytes"]
    monkeypatch.setattr(
        "agent.investigation._summarise", lambda run: {"verdict": "ALLOW", "oversized": "z" * 20000}
    )
    output = session.invoke("issue_verdict")
    assert output["state"] == "budget_exceeded"
    assert "verdict" not in output and "signature" not in output
    assert session.report()["accepted_observation_bytes"] == accepted
    assert not session.complete
    assert verify_signature(baseline.certificate)


@pytest.mark.parametrize("value", ["ordinary text", "\u91cf\u5b50\U0001f52c"])
def test_observation_accounting_includes_json_escaping(monkeypatch, value):
    from agent.investigation import ObservationLimitError

    _, _, session = setup("clean")
    payload = {"text": value}
    size = len(json.dumps(payload, ensure_ascii=True, allow_nan=False).encode("utf-8"))
    monkeypatch.setattr("agent.investigation.MAX_OBSERVATION_BYTES", size)
    monkeypatch.setattr("agent.investigation.MAX_TOTAL_OBSERVATION_BYTES", size)
    session._reserve_observation(payload)  # Exact boundary is accepted, not truncated.
    assert session.report()["accepted_observation_bytes"] == size
    with pytest.raises(ObservationLimitError):
        session._reserve_observation(payload)
    assert session.report()["accepted_observation_bytes"] == size


def test_cumulative_observation_budget_stops_the_next_action(monkeypatch):
    _, _, session = setup("clean")
    first = session.invoke("read_experiment_package")
    accepted = len(json.dumps(first, ensure_ascii=True, allow_nan=False).encode("utf-8"))
    assert session.report()["accepted_observation_bytes"] == accepted
    monkeypatch.setattr("agent.investigation.MAX_TOTAL_OBSERVATION_BYTES", accepted + 1)
    result = session.invoke("check_provenance")
    assert result["error"] == "ObservationLimitError"
    assert session.report()["accepted_observation_bytes"] == accepted
    assert session.snapshot()["allowed_actions"] == []


def test_narrator_retains_metadata_on_model_setup_failure(monkeypatch):
    root, baseline, _ = setup("clean")
    mock_sdk(monkeypatch, [])

    def fail(**kwargs):
        raise RuntimeError("PRIVATE-ERROR-MESSAGE")

    monkeypatch.setattr(sys.modules["strands.models"], "BedrockModel", fail)
    result = narrate_case(root, baseline, model_id="mock-not-live")
    assert result["status"] == "error"
    assert result["run_metadata"]["baseline_checksum"] == baseline.certificate.signature
    assert "PRIVATE-ERROR-MESSAGE" not in json.dumps(result)


def test_legacy_prose_adapter_cannot_report_false_success(monkeypatch):
    from agent.researchops_agent import run_with_model

    root, _, _ = setup("clean")
    mock_sdk(monkeypatch, ["issue_verdict"])
    with pytest.raises(RuntimeError, match="investigation_not_complete"):
        run_with_model(str(root), model_id="mock-not-live")


def test_transport_error_without_response_keeps_safe_fallback(monkeypatch):
    root, baseline, _ = setup("maya")
    original = baseline.certificate.model_dump_json()
    mock_sdk(monkeypatch, [])

    class TransportError(Exception):
        response = None

    def fail(**kwargs):
        raise TransportError("PRIVATE-ENDPOINT-AND-CREDENTIAL-MARKER")

    monkeypatch.setattr(sys.modules["strands.models"], "BedrockModel", fail)
    result = narrate_case(root, baseline, model_id="mock-not-live")
    assert result["status"] == "error"
    assert result["error_code"] == "TransportError"
    assert result["run_metadata"]["baseline_checksum"] == baseline.certificate.signature
    assert result["investigation"]["investigation_complete"] is False
    assert "PRIVATE-ENDPOINT-AND-CREDENTIAL-MARKER" not in json.dumps(result)
    assert baseline.certificate.model_dump_json() == original
    assert verify_signature(baseline.certificate)
