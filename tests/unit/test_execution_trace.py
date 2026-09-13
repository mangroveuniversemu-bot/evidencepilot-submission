"""Traces have to be stable and have to record failures."""

from __future__ import annotations

from evidence.execution_trace import Tracer, digest


def test_digest_is_stable_and_order_independent():
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    assert digest({"a": 1}) != digest({"a": 2})
    assert len(digest("x")) == 16


def test_steps_are_numbered_in_order():
    tracer = Tracer()
    for name in ("one", "two", "three"):
        with tracer.step(name, {}) as step:
            step.result = name
    trace = tracer.build()
    assert [s.index for s in trace.steps] == [1, 2, 3]
    assert [s.tool for s in trace.steps] == ["one", "two", "three"]


def test_a_failing_step_is_recorded_and_the_error_propagates():
    tracer = Tracer()
    try:
        with tracer.step("boom", {"arg": 1}):
            raise ValueError("detector table unreadable")
    except ValueError:
        pass
    step = tracer.build().steps[0]
    assert step.outcome == "error:ValueError"
    assert step.tool == "boom"
