"""Explain a disagreement instead of merely reporting one.

When an independent replay lands somewhere other than the submitted number,
"the numbers disagree" is a weak finding. A useful finding names the single
analysis step that, if changed, reproduces the submitted number exactly.

The search space is small, declared, and deterministic: each candidate is a
named deviation from the registered convention. A deviation only counts as the
root cause when it reproduces the claimed statistic *and* the claimed per-pair
correlations, because different mistakes can land on the same S.
"""

from __future__ import annotations

from agent.schemas import (
    ClaimedAnalysis,
    Convention,
    CountRow,
    Deviation,
    RootCauseCandidate,
    RootCauseReport,
)
from tools.chsh_replay import ReplayError, compute_chsh, has_flagged_subruns


def _tolerance(value: float) -> float:
    """Half a unit in the last reported decimal place, floored at 5e-4.

    A claim written as ``2.61`` asserts nothing finer than +/-0.005, so a
    candidate that lands within that window has reproduced it as stated.
    """
    text = f"{value!r}"
    decimals = len(text.split(".")[1]) if "." in text else 0
    return max(0.5 * (10.0**-decimals), 5e-4)


def enumerate_deviations(counts: list[CountRow], convention: Convention) -> list[Deviation]:
    """Every analysis mistake this agent knows how to reproduce on purpose."""
    deviations: list[Deviation] = []

    non_standard = [
        block_id
        for block_id, block in sorted(convention.blocks.items())
        if block.bob_channel_map != "standard" or block.alice_channel_map != "standard"
    ]
    for block_id in non_standard:
        block = convention.blocks[block_id]
        deviations.append(
            Deviation(
                deviation_id=f"no_channel_correction:{block_id}",
                family="measurement_convention",
                target=block_id,
                description=(
                    f"Registered channel correction for {block_id} "
                    f"(alice={block.alice_channel_map}, bob={block.bob_channel_map}) "
                    "was declared but not applied."
                ),
            )
        )
    if len(non_standard) > 1:
        deviations.append(
            Deviation(
                deviation_id="no_channel_correction:ALL",
                family="measurement_convention",
                target="ALL",
                description="No registered channel correction was applied to any block.",
            )
        )

    for pair, sign in sorted(convention.chsh_combination.items()):
        deviations.append(
            Deviation(
                deviation_id=f"flip_term_sign:{pair}",
                family="combination_formula",
                target=pair,
                description=(
                    f"The CHSH term for {pair} was combined with sign {-sign:+d} "
                    f"instead of the registered {sign:+d}."
                ),
            )
        )

    if has_flagged_subruns(counts):
        deviations.append(
            Deviation(
                deviation_id="post_selection:drop_flagged",
                family="post_selection",
                target="flagged_subruns",
                description="Flagged acquisition sub-runs were silently dropped.",
            )
        )
        deviations.append(
            Deviation(
                deviation_id="post_selection:keep_flagged",
                family="post_selection",
                target="flagged_subruns",
                description="Flagged acquisition sub-runs were silently kept.",
            )
        )

    return deviations


def _replay_deviation(deviation: Deviation, counts: list[CountRow], convention: Convention):
    kwargs: dict[str, object] = {}
    working = convention

    if deviation.family == "measurement_convention":
        if deviation.target == "ALL":
            kwargs["channel_corrections"] = False
        else:
            patched = {
                bid: (
                    block.model_copy(
                        update={"alice_channel_map": "standard", "bob_channel_map": "standard"}
                    )
                    if bid == deviation.target
                    else block
                )
                for bid, block in convention.blocks.items()
            }
            working = convention.model_copy(update={"blocks": patched})
    elif deviation.family == "combination_formula":
        pair = deviation.target
        kwargs["sign_overrides"] = {pair: -convention.chsh_combination[pair]}
    elif deviation.family == "post_selection":
        kwargs["include_flagged"] = deviation.deviation_id.endswith("keep_flagged")

    return compute_chsh(counts, working, **kwargs)  # type: ignore[arg-type]


def find_root_cause(
    counts: list[CountRow], convention: Convention, claim: ClaimedAnalysis
) -> RootCauseReport:
    """Replay each known deviation and see which one lands on the claim."""
    value_tol = _tolerance(claim.value)
    pair_tol = (
        min((_tolerance(v) for v in claim.per_pair_correlation.values()), default=5e-4)
        if claim.per_pair_correlation
        else 5e-4
    )

    candidates: list[RootCauseCandidate] = []
    for deviation in enumerate_deviations(counts, convention):
        try:
            result = _replay_deviation(deviation, counts, convention)
        except ReplayError:
            continue  # a deviation that cannot even be computed is not an explanation
        per_pair = result.per_pair()
        matches_value = abs(result.s_value - claim.value) <= value_tol
        if claim.per_pair_correlation:
            matches_per_pair = all(
                pair in per_pair and abs(per_pair[pair] - expected) <= pair_tol
                for pair, expected in claim.per_pair_correlation.items()
            )
        else:
            matches_per_pair = matches_value
        candidates.append(
            RootCauseCandidate(
                deviation=deviation,
                s_value=result.s_value,
                per_pair=per_pair,
                matches_value=matches_value,
                matches_per_pair=matches_per_pair,
            )
        )

    value_matches = tuple(c.deviation.deviation_id for c in candidates if c.matches_value)
    full_matches = tuple(c.deviation.deviation_id for c in candidates if c.is_full_match)

    if len(full_matches) == 1:
        identified = next(c for c in candidates if c.deviation.deviation_id == full_matches[0])
        conclusion = identified.deviation.description
        if len(value_matches) > 1:
            conclusion += (
                f" ({len(value_matches)} deviations reproduce the claimed value; the reported "
                "per-pair correlations single this one out.)"
            )
    elif len(full_matches) > 1:
        conclusion = (
            f"{len(full_matches)} distinct deviations reproduce the claim exactly "
            f"({', '.join(full_matches)}). The root cause is ambiguous from the submitted "
            "artifacts alone."
        )
    elif value_matches:
        conclusion = (
            f"{len(value_matches)} deviation(s) reproduce the claimed value but none reproduce "
            "the reported per-pair correlations. The submitted analysis differs from the "
            "registered convention in more than one place."
        )
    else:
        conclusion = (
            "No single known deviation from the registered convention reproduces the claim. "
            "The submitted analysis script is required to go further."
        )

    return RootCauseReport(
        candidates=tuple(candidates),
        value_matches=value_matches,
        full_matches=full_matches,
        conclusion=conclusion,
    )
