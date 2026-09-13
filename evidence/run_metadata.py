"""Public-safe run configuration fingerprints, not credentials or attestation."""

import hashlib
import platform
import uuid
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from agent.schemas import EvidenceCertificate
from evidence.execution_trace import utc_now

ROOT = Path(__file__).resolve().parents[1]


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def source_fingerprint() -> str:
    digest = hashlib.sha256()
    # Only project code, never credentials, local git configuration or private inputs.
    paths = [
        path
        for directory in ("agent", "app", "evidence", "policy", "tools")
        for path in (ROOT / directory).rglob("*.py")
    ]
    paths.extend(ROOT / name for name in ("agentcore_app.py", "pyproject.toml"))
    for path in sorted(path for path in paths if path.is_file()):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8") + b"\0")
        digest.update(bytes.fromhex(_sha(path.read_bytes())))
    return digest.hexdigest()


def build_run_metadata(
    certificate: EvidenceCertificate, *, model_id: str, region: str, prompt: str, limits: dict
) -> dict:
    dependencies = {}
    for distribution in ("pydantic", "strands-agents", "bedrock-agentcore", "boto3", "botocore"):
        try:
            dependencies[distribution] = version(distribution)
        except PackageNotFoundError:
            dependencies[distribution] = None
    # Account-specific ARN identifiers stay outside portable reports.
    model_label = (
        model_id if not model_id.startswith("arn:") and len(model_id) <= 256 else "redacted"
    )
    return {
        "schema_version": "1",
        "run_id": f"RUN-{uuid.uuid4().hex}",
        "started_at": utc_now(),
        "baseline_certificate_id": certificate.certificate_id,
        "baseline_checksum": certificate.signature,
        "source_sha256": source_fingerprint(),
        "prompt_sha256": _sha(prompt.encode("utf-8")),
        "tool_versions": dict(certificate.tool_versions),
        "python": platform.python_version(),
        "dependencies": dependencies,
        "model": {
            "id": model_label or None,
            "id_sha256": _sha(model_id.encode("utf-8")) if model_id else None,
            "region": region,
            "resolved_weights_revision": None,
            "temperature": 0.0,
        },
        "limits": dict(limits),
        "note": (
            "Configuration fingerprints, not authenticated attestation "
            "or deterministic model output."
        ),
    }
