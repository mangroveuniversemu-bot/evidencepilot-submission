"""Finite searches over open problems, kept honestly labelled.

This module exists to test one product rule, not to advance number theory: an
agent that searches ten million integers and finds no counterexample has
produced evidence, not a theorem. ``evidence/certificate.py`` refuses to issue
a certificate for one of these results unless the limitation is carried
verbatim.
"""

from __future__ import annotations

import time

from agent.schemas import BenchmarkResult

FINITE_VERIFICATION_LIMITATION = "FINITE VERIFICATION PASS != PROOF"


def collatz_steps(n: int, ceiling: int) -> tuple[int, int, bool]:
    """Iterate 3n+1 until the trajectory drops below its start value.

    Every integer below ``n`` has already been checked, so falling below the
    start is sufficient. Returns (steps, peak, reached_known_territory).
    """
    steps = 0
    peak = n
    value = n
    while value >= n:
        value = value // 2 if value % 2 == 0 else 3 * value + 1
        peak = max(peak, value)
        steps += 1
        if value == 1:
            return steps, peak, True
        if steps > ceiling:
            return steps, peak, False
    return steps, peak, True


def verify_collatz(limit: int, *, step_ceiling: int = 100_000) -> BenchmarkResult:
    """Check the Collatz trajectory of every 1 <= n <= limit."""
    started = time.perf_counter()
    counterexamples: list[int] = []
    max_steps = 0
    max_peak = 0
    for n in range(1, limit + 1):
        steps, peak, converged = collatz_steps(n, step_ceiling)
        if not converged:
            counterexamples.append(n)
        max_steps = max(max_steps, steps)
        max_peak = max(max_peak, peak)
    return BenchmarkResult(
        benchmark_id=f"collatz-finite-{limit}",
        limit=limit,
        cases_tested=limit,
        counterexamples=tuple(counterexamples),
        max_steps=max_steps,
        max_peak=max_peak,
        elapsed_s=time.perf_counter() - started,
    )
