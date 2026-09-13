"""Offline demo is explicitly not a live agent and preserves policy output."""

import json

import pytest

from app.demo import main, run_demo
from app.poc import CASES


@pytest.mark.parametrize("case", CASES)
def test_demo_keeps_sections_separate(case):
    result = run_demo(case)
    assert result["mode"] == "verification_only"
    assert result["live_model_tested"] is False
    assert result["verification"]["integrity_valid"] is True
    assert result["ai_advisory"]["status"] == "not_requested"
    assert result["human_attention"]["decision_recording_supported"] is False
    if case == "human_decision":
        assert result["verification"]["verdict"] == "HUMAN_DECISION"
        assert result["human_attention"]["escalation"]["recommended_option_id"] is None


def test_demo_all(capsys):
    assert main(["--case", "all"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert [item["case"] for item in output] == list(CASES)


def test_unknown_case_rejected():
    assert run_demo("../../private")["error"] == "invalid_request"
