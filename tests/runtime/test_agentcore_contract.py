"""Exercise the actual SDK HTTP contract without AWS calls."""

import pytest

pytest.importorskip("bedrock_agentcore")
pytest.importorskip("strands")

from starlette.testclient import TestClient  # noqa: E402

from agent.poc_narrator import build_bound_tools  # noqa: E402
from agent.researchops_agent import verify_package  # noqa: E402
from agentcore_app import app  # noqa: E402
from app.poc import CASES, EXAMPLES  # noqa: E402


def test_health_and_invocations():
    with TestClient(app) as client:
        assert client.get("/ping").status_code == 200
        response = client.post("/invocations", json={"case": "maya", "narrate": False})
        assert response.status_code == 200
        body = response.json()
        assert body["certificate"]["verdict_card"]["verdict"] == "BLOCK"
        assert body["certificate"]["verdict_card"]["fired_rule"] == "R-005"
        assert body["certificate_integrity_valid"]


def test_runtime_rejects_paths():
    with TestClient(app) as client:
        response = client.post("/invocations", json={"case": "../../.aws"})
        assert response.json()["error"] == "invalid_request"


def test_strands_tool_schemas_have_no_caller_arguments():
    root = EXAMPLES / CASES["maya"] / "inputs"
    tools = build_bound_tools(root, verify_package(root), [])
    assert len(tools) == 5
    for tool in tools:
        assert tool.tool_spec["inputSchema"]["json"].get("properties", {}) == {}
