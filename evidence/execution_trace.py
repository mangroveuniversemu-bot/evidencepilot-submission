"""Record what ran, in what order, on what bytes.

The trace is what makes a verdict re-checkable by someone who does not trust
the agent: same inputs, same tool order, same digests.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from agent.schemas import ExecutionTrace, TraceStep


def digest(value: Any) -> str:
    """Stable short digest of any JSON-serialisable value."""
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Tracer:
    """Collects one TraceStep per tool invocation."""

    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or f"TRC-{uuid.uuid4().hex[:12]}"
        self.started_at = utc_now()
        self._steps: list[TraceStep] = []

    def record(self, tool: str, args: Any, outcome: str, result: Any) -> None:
        self._steps.append(
            TraceStep(
                index=len(self._steps) + 1,
                tool=tool,
                args_digest=digest(args),
                duration_ms=0.0,
                outcome=outcome,
                result_digest=digest(result),
            )
        )

    def step(self, tool: str, args: Any):
        """Context manager that times a tool call and records its outcome."""
        return _Step(self, tool, args)

    def build(self) -> ExecutionTrace:
        return ExecutionTrace(
            trace_id=self.trace_id, started_at=self.started_at, steps=tuple(self._steps)
        )


class _Step:
    def __init__(self, tracer: Tracer, tool: str, args: Any) -> None:
        self._tracer = tracer
        self._tool = tool
        self._args = args
        self._start = 0.0
        self.result: Any = None

    def __enter__(self) -> _Step:
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        elapsed_ms = (time.perf_counter() - self._start) * 1000.0
        outcome = "ok" if exc_type is None else f"error:{exc_type.__name__}"
        result = self.result if exc_type is None else str(exc)
        self._tracer._steps.append(
            TraceStep(
                index=len(self._tracer._steps) + 1,
                tool=self._tool,
                args_digest=digest(self._args),
                duration_ms=round(elapsed_ms, 3),
                outcome=outcome,
                result_digest=digest(result),
            )
        )
        return False
