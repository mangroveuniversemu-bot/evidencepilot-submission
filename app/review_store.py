"""Local append-only review receipts. No model, policy change, or action execution.

SQLite transactions bind one receipt to one stored certificate, including when
two browser tabs submit concurrently. Checksums detect accidental alteration;
they do not authenticate a reviewer or defend against an owner rewriting the DB.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from agent.schemas import EvidenceCertificate, HumanDecisionInput, HumanDecisionReceipt
from app.poc import CASES, handle_request
from evidence.certificate import verify_signature
from evidence.execution_trace import utc_now


class ReviewError(ValueError):
    """A fail-closed review validation failure, safe to show to the local operator."""


class DecisionConflict(ReviewError):
    """A different decision is already recorded for this certificate."""


def receipt_checksum(receipt: HumanDecisionReceipt) -> str:
    canonical = json.dumps(
        receipt.model_dump(mode="json", exclude={"checksum"}),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_receipt(receipt: HumanDecisionReceipt, certificate: EvidenceCertificate) -> None:
    card = certificate.verdict_card
    escalation = card.escalation
    if (
        receipt.checksum != receipt_checksum(receipt)
        or receipt.certificate_id != certificate.certificate_id
        or receipt.certificate_sha256 != certificate.signature
        or receipt.original_verdict != card.verdict
        or receipt.original_claim_state != card.claim_state
        or escalation is None
        or receipt.escalation_id != escalation.escalation_id
        or receipt.selected_option not in escalation.options
    ):
        raise ReviewError("Decision record integrity check failed; do not rely on this record.")


class ReviewStore:
    """The local UI's persistence layer. No update/delete API is exposed."""

    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "reviews.sqlite3"
        if self.database.is_symlink():
            raise ReviewError("The review database must not be a symbolic link.")
        with closing(self._connect()) as connection, connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    certificate_id TEXT PRIMARY KEY,
                    case_name TEXT NOT NULL,
                    certificate_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    certificate_id TEXT PRIMARY KEY REFERENCES runs(certificate_id),
                    receipt_json TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS runs_no_update BEFORE UPDATE ON runs
                    BEGIN SELECT RAISE(ABORT, 'runs are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS runs_no_delete BEFORE DELETE ON runs
                    BEGIN SELECT RAISE(ABORT, 'runs are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS decisions_no_update BEFORE UPDATE ON decisions
                    BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON decisions
                    BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END;
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def create_run(self, case: str) -> dict:
        if case not in CASES:
            raise ReviewError("Choose one of the bundled synthetic cases.")
        # Only this server-side verifier may create the certificate; never accept
        # a client-submitted certificate, verdict, path, or model response.
        result = handle_request({"case": case, "narrate": False})
        certificate = EvidenceCertificate.model_validate(result["certificate"])
        if not result["ok"] or not verify_signature(certificate):
            raise ReviewError("Verification did not produce an integrity-valid certificate.")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?)",
                (
                    certificate.certificate_id,
                    case,
                    certificate.model_dump_json(),
                    certificate.issued_at,
                ),
            )
        return self.get_run(certificate.certificate_id)

    @staticmethod
    def _read_run(connection: sqlite3.Connection, certificate_id: str) -> dict:
        row = connection.execute(
            "SELECT * FROM runs LEFT JOIN decisions USING(certificate_id) WHERE certificate_id = ?",
            (certificate_id,),
        ).fetchone()
        if row is None:
            raise KeyError("Review run not found.")
        certificate = EvidenceCertificate.model_validate_json(row["certificate_json"])
        if certificate.certificate_id != certificate_id or not verify_signature(certificate):
            raise ReviewError("Certificate integrity check failed; do not rely on this record.")
        receipt = None
        if row["receipt_json"]:
            receipt = HumanDecisionReceipt.model_validate_json(row["receipt_json"])
            validate_receipt(receipt, certificate)
        return {
            "case": row["case_name"],
            "mode": "verification_only",
            "live_model_tested": False,
            "data_origin": "bundled_synthetic_fixture",
            "certificate": certificate.model_dump(mode="json"),
            "certificate_integrity_valid": True,
            "decision": receipt.model_dump(mode="json") if receipt else None,
            "decision_integrity_valid": True if receipt else None,
        }

    def get_run(self, certificate_id: str) -> dict:
        with closing(self._connect()) as connection:
            return self._read_run(connection, certificate_id)

    def list_runs(self) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT certificate_id FROM runs ORDER BY rowid DESC LIMIT 100"
            ).fetchall()
            result = []
            for row in rows:
                run = self._read_run(connection, row["certificate_id"])
                cert = run["certificate"]
                decision = run["decision"]
                result.append(
                    {
                        "certificate_id": cert["certificate_id"],
                        "case": run["case"],
                        "issued_at": cert["issued_at"],
                        "verdict": cert["verdict_card"]["verdict"],
                        "decision_id": decision["decision_id"] if decision else None,
                        "recorded_at": decision["recorded_at"] if decision else None,
                        "needs_decision": cert["verdict_card"]["escalation"] is not None,
                    }
                )
            return result

    def record_decision(self, certificate_id: str, choice: HumanDecisionInput) -> dict:
        with closing(self._connect()) as connection, connection:
            # Acquire a write lock before reading: concurrent requests cannot
            # replace each other, and an identical retry returns the same receipt.
            connection.execute("BEGIN IMMEDIATE")
            run = self._read_run(connection, certificate_id)
            certificate = EvidenceCertificate.model_validate(run["certificate"])
            card = certificate.verdict_card
            escalation = card.escalation
            if certificate.signature != choice.certificate_sha256:
                raise ReviewError("The certificate changed or does not match the reviewed run.")
            if escalation is None:
                raise ReviewError("This certificate has no human escalation to record.")
            option = next(
                (item for item in escalation.options if item.option_id == choice.option_id), None
            )
            if option is None:
                raise ReviewError("Choose an option offered by this certificate.")
            previous = run["decision"]
            if previous:
                if (
                    previous["selected_option"]["option_id"] == choice.option_id
                    and previous["actor_display_name"] == choice.actor_display_name
                    and previous["reason"] == choice.reason
                ):
                    return run
                raise DecisionConflict(
                    "A decision is already recorded. It cannot be overwritten; "
                    "start a new verification run to record a different intent."
                )
            receipt = HumanDecisionReceipt(
                decision_id=f"DEC-{uuid.uuid4().hex}",
                recorded_at=utc_now(),
                certificate_id=certificate_id,
                certificate_sha256=certificate.signature,
                escalation_id=escalation.escalation_id,
                selected_option=option,
                actor_display_name=choice.actor_display_name,
                reason=choice.reason,
                original_verdict=card.verdict,
                original_claim_state=card.claim_state,
            )
            receipt = receipt.model_copy(update={"checksum": receipt_checksum(receipt)})
            connection.execute(
                "INSERT INTO decisions VALUES (?, ?)", (certificate_id, receipt.model_dump_json())
            )
            return self._read_run(connection, certificate_id)
