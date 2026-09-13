"""Stateful, case-bound execution with separate agent and verification traces.

The independent baseline remains available without a model. This session must
actually collect evidence and reproduce its verdict card before disclosing the
baseline certificate to the model. Neither prose nor caller paths are inputs.
"""

from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path

from agent.limits import MAX_OBSERVATION_BYTES, MAX_TOOL_ATTEMPTS, MAX_TOTAL_OBSERVATION_BYTES
from agent.researchops_agent import VerificationRun, _build_replay_report, _summarise
from agent.state import Assessment
from evidence.execution_trace import Tracer, digest
from evidence.verdict_card import build_verdict_card
from policy.escalation import build_escalation
from policy.investigation import InvestigationState, after_provenance, after_replay, allowed_actions
from policy.verdict_rules import apply_rules
from tools.artifact_reader import hash_package, read_package
from tools.provenance_checker import check_provenance
from tools.root_cause import find_root_cause

TOOL_NAMES = (
    "read_experiment_package",
    "check_provenance",
    "replay_chsh",
    "search_root_cause",
    "issue_verdict",
)


class InputsChangedError(RuntimeError):
    """Input bytes changed since the independent baseline was produced."""


class BaselineMismatchError(RuntimeError):
    """Collected evidence did not reproduce the independent verdict card."""


class ObservationLimitError(RuntimeError):
    """The model-visible payload exceeds the host-owned byte allowance."""


class Investigation:
    """One invocation, one host-selected package, no model-editable state."""

    def __init__(self, root: Path, baseline: VerificationRun):
        self._root = root.resolve()
        self._baseline = baseline.model_copy(deep=True)
        if self._root != Path(baseline.assessment.package.root).resolve():
            raise ValueError("baseline_package_mismatch")
        self._hashes = dict(baseline.certificate.input_hashes)
        self._state = InvestigationState.NEW
        self._package = None
        self._provenance = None
        self._replay = None
        self._replay_error = None
        self._root_cause = None
        self._agent_trace: list[dict] = []
        self._verification = Tracer()
        self._attempts = 0
        self._observation_bytes = 0
        self._lock = threading.RLock()

    @property
    def complete(self) -> bool:
        return self._state is InvestigationState.COMPLETE

    @property
    def terminal(self) -> bool:
        return not allowed_actions(self._state)

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot_for(self._state)

    def _snapshot_for(self, state: InvestigationState) -> dict:
        return {
            "state": state.value,
            "allowed_actions": list(allowed_actions(state)),
            "investigation_complete": state is InvestigationState.COMPLETE,
            "tool_attempts": self._attempts,
            "baseline_certificate_id": self._baseline.certificate.certificate_id,
            "human_attention_required": (
                self._baseline.card.escalation is not None
                if state is InvestigationState.COMPLETE
                else None
            ),
            "human_decision_recorded": False,
        }

    def report(self) -> dict:
        with self._lock:
            return {
                **self.snapshot(),
                "agent_trace": copy.deepcopy(self._agent_trace),
                "verification_trace": self._verification.build().model_dump(mode="json"),
                "accepted_observation_bytes": self._observation_bytes,
            }

    def _check_inputs(self) -> None:
        if hash_package(self._root) != self._hashes:
            raise InputsChangedError("inputs_changed")

    def _reserve_observation(self, payload: dict) -> None:
        # ASCII JSON conservatively accounts for Unicode escaping. These are
        # payload bytes, not model tokens or SDK envelope overhead.
        size = len(json.dumps(payload, ensure_ascii=True, allow_nan=False).encode("utf-8"))
        if (
            size > MAX_OBSERVATION_BYTES
            or self._observation_bytes + size > MAX_TOTAL_OBSERVATION_BYTES
        ):
            raise ObservationLimitError("observation_limit")
        self._observation_bytes += size

    def invoke(self, action: str) -> dict:
        # SDK tools may be scheduled concurrently; transitions must be atomic.
        with self._lock:
            before = self._state.value
            if self._attempts >= MAX_TOOL_ATTEMPTS:
                # One overflow record only: malicious repeated calls cannot grow the log.
                if not self.terminal:
                    self._state = InvestigationState.BUDGET_EXCEEDED
                    self._record("tool_budget", before, "rejected", 0.0, {"error": "tool_budget"})
                return {"error": "tool_budget", **self.snapshot()}
            self._attempts += 1
            started = time.monotonic()
            outcome = "ok"
            safe_action = action if action in TOOL_NAMES else "unknown_tool"
            if action not in allowed_actions(self._state):
                outcome = "rejected"
                result = {"error": "action_not_allowed"}
            else:
                try:
                    self._check_inputs()
                    result, next_state = self._execute(action)
                    self._check_inputs()
                    self._reserve_observation({**result, **self._snapshot_for(next_state)})
                    self._state = next_state
                except Exception as exc:
                    # No raw exception messages: they may contain paths or account data.
                    self._state = (
                        InvestigationState.INVALIDATED
                        if isinstance(exc, InputsChangedError)
                        else InvestigationState.BUDGET_EXCEEDED
                        if isinstance(exc, ObservationLimitError)
                        else InvestigationState.FAILED
                    )
                    outcome = "error"
                    result = {"error": type(exc).__name__}
            self._record(safe_action, before, outcome, time.monotonic() - started, result)
            return {**copy.deepcopy(result), **self.snapshot()}

    def _record(self, action: str, before: str, outcome: str, elapsed: float, result: dict):
        self._agent_trace.append(
            {
                "index": len(self._agent_trace) + 1,
                "action": action,
                "state_before": before,
                "state_after": self._state.value,
                "outcome": outcome,
                "duration_ms": round(elapsed * 1000, 3),
                "observation_digest": digest(result),
            }
        )

    def _execute(self, action: str) -> tuple[dict, InvestigationState]:
        if action == "read_experiment_package":
            with self._verification.step("artifact_reader.read_package", {}) as step:
                self._package = read_package(self._root)
                p = self._package
                result = {
                    "package_id": p.manifest.package_id,
                    "experiment_id": p.manifest.experiment_id,
                    "claim_id": p.claim.claim_id,
                    "claimed_statistic": p.claim.statistic,
                    "claimed_value": p.claim.value,
                    "convention_id": p.convention.convention_id,
                    "acquisition_rows": len(p.counts),
                    "flagged_subruns": [f"{r.block_id}/{r.subrun_id}" for r in p.counts if r.flags],
                }
                step.result = result
            return result, InvestigationState.PACKAGE_READ

        if action == "check_provenance":
            with self._verification.step("provenance_checker.check_provenance", {}) as step:
                self._provenance = check_provenance(self._package)
                result = {
                    "complete": self._provenance.complete,
                    "critical": bool(self._provenance.critical),
                    "findings": [f.model_dump(mode="json") for f in self._provenance.findings],
                }
                step.result = result
            return result, after_provenance(self._provenance)

        if action == "replay_chsh":
            self._replay, self._replay_error = _build_replay_report(
                self._package, self._verification
            )
            result = {
                "replay": self._replay.model_dump(mode="json") if self._replay else None,
                "replay_failed": self._replay_error is not None,
            }
            return result, after_replay(self._replay)

        if action == "search_root_cause":
            with self._verification.step("root_cause.find_root_cause", {}) as step:
                p = self._package
                self._root_cause = find_root_cause(p.counts, p.convention, p.claim)
                result = {
                    "conclusion": self._root_cause.conclusion,
                    "value_matches": list(self._root_cause.value_matches),
                    "full_matches": list(self._root_cause.full_matches),
                    "identified": (
                        self._root_cause.identified.model_dump(mode="json")
                        if self._root_cause.identified
                        else None
                    ),
                }
                step.result = result
            return result, InvestigationState.READY_TO_ISSUE

        # The legal-action policy reaches here only for issue_verdict.
        assessment = Assessment(
            package=self._package,
            provenance=self._provenance,
            replay=self._replay,
            replay_error=self._replay_error,
            root_cause=self._root_cause,
        )
        with self._verification.step("verdict_rules.apply_rules", {}) as step:
            rule = apply_rules(assessment)
            step.result = {"rule": rule.rule_id, "verdict": rule.verdict.value}
        deadline = self._baseline.card.escalation
        escalation = build_escalation(
            assessment, rule, deadline_note=deadline.deadline_note if deadline else ""
        )
        card = build_verdict_card(assessment, rule, escalation)
        if card.model_dump(mode="json") != self._baseline.card.model_dump(mode="json"):
            raise BaselineMismatchError("baseline_mismatch")
        # Release the canonical, immutable certificate only after independently
        # deriving its card from this session's actual accumulated tool results.
        return copy.deepcopy(_summarise(self._baseline)), InvestigationState.COMPLETE
