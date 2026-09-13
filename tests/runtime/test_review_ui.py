"""Offline HTTP contract and drive-by browser request protections."""

import subprocess
import sys

import pytest

pytest.importorskip("starlette")
pytest.importorskip("httpx")

from starlette.testclient import TestClient  # noqa: E402

from app.review_ui import create_app  # noqa: E402

ORIGIN = "http://127.0.0.1:8765"


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "review"), base_url=ORIGIN) as client:
        session = client.get("/api/session").json()
        client.headers.update({"Origin": ORIGIN, "X-Review-Token": session["token"]})
        yield client


def test_assets_and_browser_boundary_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Verification-only rehearsal" in response.text
    assert 'id="decision-form" hidden' in response.text
    assert 'id="ack" type="checkbox" required' in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert client.get("/static/review.css").status_code == 200
    js = client.get("/static/review.js").text
    assert "innerHTML" not in js and "eval(" not in js
    assert ".textContent" in js and ".reset()" in js
    assert "checked = true" not in js
    assert client.get("/static/review_store.py").status_code == 404


def test_full_record_export_and_history(client):
    response = client.post("/api/runs", json={"case": "human_decision"})
    assert response.status_code == 201
    result = response.json()
    cert = result["certificate"]
    cert_id = cert["certificate_id"]
    assert cert["verdict_card"]["escalation"]["recommended_option_id"] is None
    payload = {
        "certificate_sha256": cert["signature"],
        "option_id": "DEFER_PENDING_INSTRUMENT_LOG",
        "actor_display_name": "QA <script> reviewer",
        "reason": "QA <img src=x onerror=alert(1)> only; rendered as text, not HTML.",
    }
    response = client.post(f"/api/runs/{cert_id}/decision", json=payload)
    assert response.status_code == 200
    saved = response.json()
    assert saved["certificate"] == cert
    assert saved["decision"]["reason"] == payload["reason"]
    assert saved["decision"]["action_executed"] is False
    assert client.get(f"/api/runs/{cert_id}").json() == saved
    export = client.get(f"/api/runs/{cert_id}/export")
    assert export.json() == saved
    assert "attachment" in export.headers["content-disposition"]
    assert client.post(f"/api/runs/{cert_id}/decision", json=payload).json() == saved
    assert (
        client.post(
            f"/api/runs/{cert_id}/decision", json=payload | {"reason": "Different intent"}
        ).status_code
        == 409
    )
    assert (
        client.get("/api/runs").json()["runs"][0]["decision_id"] == saved["decision"]["decision_id"]
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://untrusted.example"},
        {"Origin": "null"},
        {"Origin": ""},
        {"X-Review-Token": "wrong"},
        {"Host": "rebind.example:8765"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_rejects_cross_origin_and_missing_write_token(client, headers):
    response = client.post("/api/runs", json={"case": "maya"}, headers=headers)
    assert response.status_code == 403
    assert client.get("/api/runs").json()["runs"] == []


def test_external_site_cannot_read_bootstrap(client):
    assert (
        client.get("/api/session", headers={"Origin": "https://untrusted.example"}).status_code
        == 403
    )
    assert client.get("/api/session", headers={"Host": "untrusted.example"}).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"case": "../../.aws"},
        {"case": "maya", "narrate": True},
        {"case": "maya", "verdict": "ALLOW"},
        {},
        {"case": 1},
    ],
)
def test_rejects_live_calls_paths_and_client_verdicts(client, payload):
    assert client.post("/api/runs", json=payload).status_code == 400
    assert client.get("/api/runs").json()["runs"] == []


def test_body_limit_content_type_and_invalid_json(client):
    assert client.post("/api/runs", content="plain text").status_code == 415
    assert client.post("/api/runs", json={"case": "x" * 17000}).status_code == 413
    assert (
        client.post(
            "/api/runs", content="{", headers={"Content-Type": "application/json"}
        ).status_code
        == 400
    )
    assert client.get("/api/runs/unknown/export").status_code == 404


def test_ui_import_does_not_import_cloud_sdk():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.review_ui, sys; assert not any(m.split('.')[0] in {'boto3', 'botocore', 'strands'} for m in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
