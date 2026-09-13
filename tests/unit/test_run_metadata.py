"""Run reports expose configuration fingerprints, never AWS credentials."""

import hashlib
import json

import pytest

from agent.limits import configured_limits
from evidence.run_metadata import build_run_metadata, source_fingerprint


def metadata(certificate, **overrides):
    arguments = {
        "model_id": "mock-not-live",
        "region": "ap-southeast-2",
        "prompt": "Test instructions",
        "limits": configured_limits(),
    }
    return build_run_metadata(certificate, **(arguments | overrides))


def test_same_configuration_is_comparable_but_runs_have_distinct_ids(maya_run):
    first, second = metadata(maya_run.certificate), metadata(maya_run.certificate)
    assert first["run_id"] != second["run_id"]
    for key in (
        "source_sha256",
        "prompt_sha256",
        "tool_versions",
        "python",
        "dependencies",
        "model",
        "limits",
    ):
        assert first[key] == second[key]
    assert first["baseline_checksum"] == maya_run.certificate.signature
    assert first["baseline_certificate_id"] == maya_run.certificate.certificate_id
    assert first["model"]["resolved_weights_revision"] is None
    assert first["tool_versions"]["verdict_rules"] == "2"


def test_changed_prompt_and_limits_are_visible(maya_run):
    original = metadata(maya_run.certificate)
    changed = metadata(
        maya_run.certificate, prompt="Changed test instructions", limits={"model_calls": 1}
    )
    assert original["prompt_sha256"] != changed["prompt_sha256"]
    assert original["source_sha256"] == changed["source_sha256"]
    assert changed["limits"] == {"model_calls": 1}


@pytest.mark.parametrize(
    "model_id", ["arn:aws:bedrock:ap-southeast-2:123456789012:inference-profile/test", "x" * 300]
)
def test_account_specific_model_identifiers_are_redacted(maya_run, monkeypatch, model_id):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "TEST-SECRET-NEVER-EXPOSE")
    report = metadata(maya_run.certificate, model_id=model_id)
    assert report["model"]["id"] == "redacted"
    assert report["model"]["id_sha256"] == hashlib.sha256(model_id.encode()).hexdigest()
    serialized = json.dumps(report)
    assert model_id not in serialized
    assert "TEST-SECRET-NEVER-EXPOSE" not in serialized
    assert "123456789012" not in serialized


def test_missing_dependency_is_reported_as_unavailable(maya_run, monkeypatch):
    from importlib.metadata import PackageNotFoundError

    def missing(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr("evidence.run_metadata.version", missing)
    assert all(value is None for value in metadata(maya_run.certificate)["dependencies"].values())


def test_source_fingerprint_tracks_code_not_secrets_or_private_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr("evidence.run_metadata.ROOT", tmp_path)
    (tmp_path / "agent").mkdir()
    source = tmp_path / "agent" / "example.py"
    source.write_text("version = 1", encoding="utf-8")
    first = source_fingerprint()
    (tmp_path / ".env").write_text("TEST-SECRET", encoding="utf-8")
    (tmp_path / "private-input.txt").write_text("PRIVATE-INPUT", encoding="utf-8")
    assert source_fingerprint() == first
    source.write_text("version = 2", encoding="utf-8")
    second = source_fingerprint()
    assert second != first
    (tmp_path / "agentcore_app.py").write_text("entrypoint = 1", encoding="utf-8")
    assert source_fingerprint() != second
