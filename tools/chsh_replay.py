"""Deterministic CHSH recomputation from raw coincidence counts.

The whole pipeline is four steps, in this order, with no model in the loop:

    raw counts -> convention correction -> E(a,b) -> S -> sigma(S)

Definitions
-----------
For one setting pair, with N the total number of coincidences,

    E = (N++ + N-- - N+- - N-+) / N

For an independent +/-1 sample with population mean mu, Var(E) = (1 - mu^2) / N.
Replacing mu with the observed E gives the plug-in variance estimate used here.
The CHSH statistic is a signed sum over the four setting pairs, with the signs
taken from the *registered convention file* rather than hardcoded here:

    S = sum_pair  sign(pair) * E(pair)

Local hidden variable models obey |S| <= 2 (the classical bound). Quantum
mechanics caps the expectation |S| at 2*sqrt(2), not every finite-sample estimate.
The plug-in uncertainty below assumes independent sampling and is not a rigorous
finite-sample confidence interval or a loophole-free Bell test.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from agent.schemas import (
    PAIR_ORDER,
    CHSHResult,
    Convention,
    Correlation,
    CountRow,
)


class ReplayError(ValueError):
    """Raised when the package cannot be replayed at all."""


def correct_counts(row: CountRow, convention: Convention) -> tuple[int, int, int, int]:
    """Apply the registered channel maps for this row's acquisition block.

    Counts arrive labelled the way the detectors wrote them. When the convention
    records that a block's channel labels were inverted, the outcome signs for
    that party flip, which permutes the four count cells.
    """
    block = convention.blocks.get(row.block_id)
    if block is None:
        raise ReplayError(f"block {row.block_id!r} has no entry in the registered convention")

    n_pp, n_pm, n_mp, n_mm = row.n_pp, row.n_pm, row.n_mp, row.n_mm

    if block.bob_channel_map == "inverted":
        # Bob's outcome sign flips: (+,+) <-> (+,-) and (-,+) <-> (-,-).
        n_pp, n_pm, n_mp, n_mm = n_pm, n_pp, n_mm, n_mp
    elif block.bob_channel_map != "standard":
        raise ReplayError(f"unknown bob_channel_map {block.bob_channel_map!r} for {row.block_id}")

    if block.alice_channel_map == "inverted":
        # Alice's outcome sign flips: (+,+) <-> (-,+) and (+,-) <-> (-,-).
        n_pp, n_pm, n_mp, n_mm = n_mp, n_mm, n_pp, n_pm
    elif block.alice_channel_map != "standard":
        raise ReplayError(
            f"unknown alice_channel_map {block.alice_channel_map!r} for {row.block_id}"
        )

    return n_pp, n_pm, n_mp, n_mm


def correlation(n_pp: int, n_pm: int, n_mp: int, n_mm: int) -> tuple[float, float, int]:
    """Return (E, sigma_E, N) for one setting pair."""
    total = n_pp + n_pm + n_mp + n_mm
    if total == 0:
        raise ReplayError("setting pair has zero coincidences; E is undefined")
    e_value = (n_pp + n_mm - n_pm - n_mp) / total
    variance = max(0.0, (1.0 - e_value * e_value)) / total
    return e_value, math.sqrt(variance), total


def _selected_rows(
    counts: Iterable[CountRow], convention: Convention, include_flagged: bool
) -> tuple[list[CountRow], list[str]]:
    kept: list[CountRow] = []
    dropped: list[str] = []
    for row in counts:
        if row.flags and not include_flagged:
            dropped.append(f"{row.block_id}/{row.subrun_id}")
        else:
            kept.append(row)
    del convention  # selection depends only on flags; kept for signature symmetry
    return kept, dropped


def compute_chsh(
    counts: Iterable[CountRow],
    convention: Convention,
    *,
    include_flagged: bool | None = None,
    channel_corrections: bool = True,
    sign_overrides: dict[str, int] | None = None,
) -> CHSHResult:
    """Recompute S from raw counts under an explicit convention.

    ``channel_corrections`` and ``sign_overrides`` exist so that
    ``tools/root_cause.py`` can replay *deliberately wrong* analyses and see
    which one reproduces a disputed number. Normal verification leaves them at
    their registered defaults.
    """
    if include_flagged is None:
        include_flagged = convention.subrun_inclusion != "unflagged_only"

    rows, dropped = _selected_rows(counts, convention, include_flagged)
    if not rows:
        raise ReplayError("every acquisition sub-run was excluded; nothing to replay")

    totals: dict[str, list[int]] = {}
    blocks: dict[str, list[str]] = {}
    for row in rows:
        block = convention.blocks.get(row.block_id)
        if block is None:
            raise ReplayError(f"block {row.block_id!r} has no entry in the registered convention")
        cells = (
            correct_counts(row, convention)
            if channel_corrections
            else (row.n_pp, row.n_pm, row.n_mp, row.n_mm)
        )
        bucket = totals.setdefault(block.pair, [0, 0, 0, 0])
        for i, value in enumerate(cells):
            bucket[i] += value
        blocks.setdefault(block.pair, [])
        if row.block_id not in blocks[block.pair]:
            blocks[block.pair].append(row.block_id)

    signs = dict(convention.chsh_combination)
    if sign_overrides:
        signs.update(sign_overrides)

    missing = [pair for pair in signs if pair not in totals]
    if missing:
        raise ReplayError(f"no surviving data for setting pair(s): {', '.join(sorted(missing))}")

    correlations: list[Correlation] = []
    s_value = 0.0
    variance = 0.0
    for pair in sorted(totals, key=lambda p: PAIR_ORDER.index(p) if p in PAIR_ORDER else 99):
        e_value, sigma, total = correlation(*totals[pair])
        correlations.append(
            Correlation(
                pair=pair,
                block_ids=tuple(blocks[pair]),
                n_total=total,
                e_value=e_value,
                sigma=sigma,
            )
        )
        s_value += signs.get(pair, 0) * e_value
        variance += (signs.get(pair, 0) ** 2) * sigma * sigma

    return CHSHResult(
        s_value=s_value,
        sigma_s=math.sqrt(variance),
        correlations=tuple(correlations),
        classical_bound=convention.classical_bound,
        tsirelson_bound=convention.tsirelson_bound,
        convention_id=convention.convention_id,
        included_subruns=tuple(f"{r.block_id}/{r.subrun_id}" for r in rows),
        excluded_subruns=tuple(dropped),
    )


def has_flagged_subruns(counts: Iterable[CountRow]) -> bool:
    return any(row.flags for row in counts)
