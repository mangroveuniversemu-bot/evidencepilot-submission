"""The human record must never cross the deterministic authority boundary."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from agent.schemas import EvidenceCertificate, HumanDecisionInput, HumanDecisionReceipt
from app.poc import CASES
from app.review_store import (
    DecisionConflict,
    ReviewError,
    ReviewStore,
    receipt_checksum,
    validate_receipt,
)
from evidence.certificate import verify_signature


@pytest.fixture
def store(tmp_path):
    return ReviewStore(tmp_path / "reviews")


def choice_for(run, **changes):
    certificate = run["certificate"]
    data = {
        "certificate_sha256": certificate["signature"],
        "option_id": certificate["verdict_card"]["escalation"]["options"][0]["option_id"],
        "actor_display_name": "QA reviewer (synthetic test)",
        "reason": "QA only: check the instrument record before a subsequent review.",
    }
    return HumanDecisionInput.model_validate(data | changes)


@pytest.mark.parametrize("case", CASES)
def test_all_cases_preserve_verifier_and_no_live_claim(store, case):
    run = store.create_run(case)
    assert run["mode"] == "verification_only"
    assert run["live_model_tested"] is False
    assert run["data_origin"] == "bundled_synthetic_fixture"
    assert run["decision"] is None
    certificate = EvidenceCertificate.model_validate(run["certificate"])
    assert verify_signature(certificate)
    if case == "human_decision":
        assert certificate.verdict_card.escalation.recommended_option_id is None


def test_receipt_persists_separately_without_changing_certificate(store):
    run = store.create_run("human_decision")
    original = run["certificate"]
    saved = store.record_decision(original["certificate_id"], choice_for(run))
    assert saved["certificate"] == original
    receipt = HumanDecisionReceipt.model_validate(saved["decision"])
    assert receipt.checksum == receipt_checksum(receipt)
    assert receipt.original_verdict == "HUMAN_DECISION"
    assert receipt.identity_assurance == "self_reported_not_authenticated"
    assert receipt.authority == "intent_only"
    assert not receipt.action_executed
    assert receipt.recorded_at.endswith("+00:00") or receipt.recorded_at.endswith("Z")
    reopened = ReviewStore(store.directory)
    assert reopened.get_run(original["certificate_id"]) == saved
    assert reopened.list_runs()[0]["decision_id"] == receipt.decision_id


def test_override_is_only_intent_and_block_is_unchanged(store):
    run = store.create_run("maya")
    result = store.record_decision(
        run["certificate"]["certificate_id"],
        choice_for(run, option_id="OVERRIDE_WITH_JUSTIFICATION"),
    )
    assert result["certificate"] == run["certificate"]
    assert result["decision"]["original_verdict"] == "BLOCK"
    assert result["decision"]["original_claim_state"] == "NOT_REPRODUCED"
    assert result["decision"]["action_executed"] is False
    assert "does not authorize" in result["decision"]["selected_option"]["consequence"]


def test_concurrent_identical_retries_return_one_receipt(store):
    run = store.create_run("maya")
    cert_id = run["certificate"]["certificate_id"]
    choice = choice_for(run)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.record_decision(cert_id, choice), range(4)))
    assert len({result["decision"]["decision_id"] for result in results}) == 1
    with sqlite3.connect(store.database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1


def test_conflicting_retry_never_overwrites(store):
    run = store.create_run("maya")
    cert_id = run["certificate"]["certificate_id"]
    original = store.record_decision(cert_id, choice_for(run))
    with pytest.raises(DecisionConflict):
        store.record_decision(cert_id, choice_for(run, reason="A different intention"))
    assert store.get_run(cert_id) == original


def test_wrong_certificate_or_option_fails_closed(store):
    first = store.create_run("maya")
    second = store.create_run("human_decision")
    second_id = second["certificate"]["certificate_id"]
    with pytest.raises(ReviewError, match="does not match"):
        store.record_decision(second_id, choice_for(first))
    with pytest.raises(ReviewError, match="offered"):
        store.record_decision(second_id, choice_for(second, option_id="AUTHORIZE_EVERYTHING"))
    assert store.get_run(second_id)["decision"] is None


def test_allow_has_no_recordable_escalation(store):
    run = store.create_run("clean")
    choice = HumanDecisionInput(
        certificate_sha256=run["certificate"]["signature"],
        option_id="APPROVE",
        actor_display_name="QA reviewer",
        reason="QA only",
    )
    with pytest.raises(ReviewError, match="no human escalation"):
        store.record_decision(run["certificate"]["certificate_id"], choice)


@pytest.mark.parametrize(
    "changes",
    [
        {"reason": "   "},
        {"reason": "x" * 2001},
        {"reason": "bad\x00text"},
        {"actor_display_name": "\n\t"},
        {"actor_display_name": "x" * 81},
        {"reason": 123},
        {"action_executed": True},
        {"certificate_sha256": "0" * 63},
        {"option_id": "../../anything"},
    ],
)
def test_input_validation(store, changes):
    with pytest.raises(ValidationError):
        choice_for(store.create_run("maya"), **changes)


@pytest.mark.parametrize("table", ["runs", "decisions"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_database_rejects_normal_update_and_delete(store, table, operation):
    run = store.create_run("maya")
    store.record_decision(run["certificate"]["certificate_id"], choice_for(run))
    with sqlite3.connect(store.database) as connection, pytest.raises(sqlite3.IntegrityError):
        if operation == "UPDATE":
            connection.execute(f"UPDATE {table} SET certificate_id = certificate_id")
        else:
            connection.execute(f"DELETE FROM {table}")


def test_tampering_detected_not_just_claimed(store):
    run = store.create_run("maya")
    saved = store.record_decision(run["certificate"]["certificate_id"], choice_for(run))
    receipt = HumanDecisionReceipt.model_validate(saved["decision"])
    certificate = EvidenceCertificate.model_validate(saved["certificate"])
    with pytest.raises(ReviewError, match="integrity"):
        validate_receipt(receipt.model_copy(update={"reason": "modified"}), certificate)
    with sqlite3.connect(store.database) as connection:
        # Simulate a local owner bypassing the append-only application guard.
        connection.execute("DROP TRIGGER runs_no_update")
        certificate.verdict_card.headline = "Altered outside the app"
        connection.execute("UPDATE runs SET certificate_json = ?", (certificate.model_dump_json(),))
    with pytest.raises(ReviewError, match="integrity"):
        store.get_run(certificate.certificate_id)
    with pytest.raises(ReviewError):
        store.list_runs()


def test_unknown_case_and_sql_input_do_not_escape_storage(store):
    with pytest.raises(ReviewError):
        store.create_run("../../.aws")
    with pytest.raises(KeyError):
        store.get_run("' OR 1=1 --")
    assert store.list_runs() == []
