"""Mechanical checks of the CHSH definition and finite-sample diagnostics.

No hypothesis test or physical certification is performed here. In particular,
an empirical value above the quantum expectation bound is not impossible.
"""

import math

from agent.schemas import PAIR_ORDER, CHSHDiagnostics, CHSHResult, ExperimentPackage

CLASSICAL_BOUND = 2.0
TSIRELSON_BOUND = 2.0 * math.sqrt(2.0)
ALGEBRAIC_BOUND = 4.0


def diagnose_chsh(package: ExperimentPackage, result: CHSHResult) -> CHSHDiagnostics:
    convention = package.convention
    signs = convention.chsh_combination
    issues = []
    if set(signs) != set(PAIR_ORDER):
        issues.append("CHSH requires exactly the four registered setting pairs.")
    if any(sign not in (-1, 1) for sign in signs.values()) or math.prod(signs.values()) != -1:
        issues.append("CHSH requires four unit coefficients with an odd number of minus signs.")
    if not math.isclose(convention.classical_bound, CLASSICAL_BOUND, rel_tol=0, abs_tol=1e-12):
        issues.append("The declared classical bound is not the standard CHSH bound.")
    if not math.isclose(convention.tsirelson_bound, TSIRELSON_BOUND, rel_tol=0, abs_tol=1e-12):
        issues.append("The declared quantum expectation bound is not the standard CHSH bound.")
    if package.claim.statistic != "CHSH_S":
        issues.append("This verifier supports only the CHSH_S statistic.")
    for row in package.counts:
        block = convention.blocks.get(row.block_id)
        if block and block.pair != f"{row.setting_a}_{row.setting_b}":
            issues.append("An acquisition setting pair disagrees with its registered block.")
            break
    return CHSHDiagnostics(
        convention_valid=not issues,
        convention_issues=tuple(issues),
        claim_in_algebraic_range=(
            math.isfinite(package.claim.value) and abs(package.claim.value) <= ALGEBRAIC_BOUND
        ),
        algebraic_bound=ALGEBRAIC_BOUND,
        empirical_above_tsirelson=abs(result.s_value) > TSIRELSON_BOUND,
        degenerate_uncertainty=any(c.sigma == 0 or c.n_total < 2 for c in result.correlations),
        minimum_pair_count=min(c.n_total for c in result.correlations),
    )
