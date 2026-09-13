# The CHSH computation

Everything in `tools/chsh_replay.py`, written out.

## Correlations

Each acquisition block records four coincidence counts for one pair of
analyser settings: `n_pp`, `n_pm`, `n_mp`, `n_mm`, where the first index is
Alice's outcome and the second is Bob's. With `N` the total,

```
E(a,b) = (n_pp + n_mm - n_pm - n_mp) / N
```

`E` is the sample mean of a variable taking values ±1. For independent,
identically distributed observations with population mean `mu`,

```
Var(E) = (1 - mu²) / N
estimated variance (plug-in) = (1 - E²) / N
```

`correlation()` returns the square root of the **plug-in estimate** as `sigma`.
It is not an exact population variance or a finite-sample confidence interval.
An all-identical sample, especially with `N = 1`, returns zero plug-in standard
error; that does not establish zero population uncertainty.

## The statistic

```
S = Σ_pair  sign(pair) · E(pair)
```

The four signs come from `chsh_combination` in the **convention file**, not
from the code. The conventional choice is

```
S = E(a,b) - E(a,b′) + E(a′,b) + E(a′,b′)
```

but which term carries the minus is a labelling choice, and a labelling choice
that lives in code is a labelling choice nobody can audit. The supported CHSH
definition has exactly four unit coefficients, with an odd number of minus
signs. `tools/chsh_diagnostics.py` checks this, the setting-pair mapping, the
statistic identifier, and the declared standard bounds. Assuming independent
acquisitions for the four setting pairs,

```
σ(S) = sqrt( Σ_pair sign(pair)² · σ(E_pair)² )
```

## Bounds

- **Algebraic range, |S| ≤ 4.** Four signed empirical correlations in `[-1, 1]`
  cannot exceed this. Once the definition is checked, an out-of-range submitted
  claim is an arithmetic error (`R-003`), not a physical hypothesis test.
- **Classical expectation bound, |S| ≤ 2.** This constrains the population
  correlations under the Bell/CHSH local-model assumptions, not every empirical
  estimate from separate finite samples.
- **Quantum expectation bound, |S| ≤ 2√2 ≈ 2.8284.** This constrains quantum
  expectation values. A finite-sample estimate can cross it; crossing alone is
  neither evidence of impossible physics nor grounds for rejecting replay.

The distinction between an expectation and its estimate is explicit in the
[formal statement of Tsirelson's bound](https://isa-afp.org/browser_info/current/AFP/TsirelsonBound/Tsirelson.html).

`CHSHResult.violates_bound` is retained as a legacy API name for the approximate
screen `(|S| - 2) / sigma_S > 3`. It is **not** a certified Bell violation,
p-value, or coverage guarantee. With zero total plug-in error the legacy boolean
is false and sigma ratios are omitted from the verdict card; a review is required.
Experimental loopholes, nonstationarity, correlated trials and post-selection
require further analysis that this verifier does not implement.

### A hand-checkable finite-sample counterexample

Take one independent product observation per setting pair, with outcomes
`(+1, -1, +1, +1)`. Then `S = 1 - (-1) + 1 + 1 = 4`. A local model with fresh,
independent fair outcomes has population correlations zero, but this particular
four-product pattern still occurs with probability `1/16`. The empirical `S = 4`
does not violate an expectation-value theorem.

The generated `case_l_finite_sample_boundary` reproduces this example and must
produce `REVIEW / REPRODUCED / REQUIRES_REVIEW`, not a physics-error BLOCK.
`case_m_algebraic_claim` uses the same counts but claims `S = 4.2`; it must BLOCK.
Independent enumeration and hand-counted tests are in
`tests/unit/test_finite_sample_semantics.py`; they do not use the replay function
to compute the counterexample's expected result.

### Verdict semantics, rule version 2

The first-match order is `R-001, R-002, R-004, R-003, R-005, R-006, R-007,
R-008, R-010, R-009`. Definition checks precede magnitude checks.

- `R-004` blocks an unsupported expression, including four all-positive
  coefficients, even if its numeric result looks plausible.
- `R-005` blocks disagreement with replay. For compatibility, agreement is
  currently defined by the larger of three plug-in standard errors and the
  claim's inferred rounding tolerance. This is not a bit-exact comparison or
  an independent-measurement significance test.
- `R-010` requires review for a reproduced estimate above the quantum expectation
  bound, or a setting pair with degenerate plug-in uncertainty.
- `R-009` accepts replay and the checked provenance only. Physical interpretation
  remains `NOT_ESTABLISHED`, including for clean ALLOW results.

The certificate separately records `claim_state` and `physical_interpretation`.
There is deliberately no `ESTABLISHED` physical-interpretation state. The new
field changes the certificate checksum payload; regenerate version-2 artifacts
from their inputs instead of silently upgrading old stored certificates.

## Measurement conventions are data

Detectors record channel numbers. Turning a channel number into an outcome
sign is a convention, and conventions drift: a fibre gets re-patched, a
polariser is remounted, one acquisition block ends up labelled with inverted
channels and the instrument log records it.

The registered convention therefore carries a per-block channel map. When a
block is marked `inverted`, Bob's outcome sign flips, which permutes the four
count cells:

```
(n_pp, n_pm, n_mp, n_mm)  →  (n_pm, n_pp, n_mm, n_mp)
```

That permutation is its own inverse, which is why the raw file and the
corrected view can be generated from one another — and why forgetting to
apply it flips the sign of `E` for that block rather than producing an
obviously broken number. A sign error that produces a *plausible* result is
the dangerous kind.

## Worked example: the hero case

`examples/maya_case` ships four blocks of 20,000 coincidences. `BLK-02`
carries a documented inverted channel map.

| pair | E, registered | E, correction dropped |
| --- | ---: | ---: |
| `a_b` | +0.7625 | +0.7625 |
| `a_bp` | **+0.3250** | **−0.3250** |
| `ap_b` | +0.7625 | +0.7625 |
| `ap_bp` | +0.7625 | +0.7625 |

```
S_registered = 0.7625 - 0.3250 + 0.7625 + 0.7625 = 1.9625 ± 0.0104
S_dropped    = 0.7625 + 0.3250 + 0.7625 + 0.7625 = 2.6125 ± 0.0104
```

2.6125 rounds to the submitted 2.61. One missing correction changes whether the
approximate classical-bound screen passes. It does not change this verifier's
inability to certify a physical Bell violation.

The two analyses read the same raw counts, so the 0.65 gap is **systematic,
not statistical** — the "62σ" figure quoted in the verdict measures the size
of the analysis discrepancy against the statistical scale, and the report says
so explicitly rather than implying two independent measurements disagreed.

## What this does not establish

A reproduced `S` means the submitted number agrees with the replay within the
configured tolerance under the checked convention. It says nothing about whether the detectors
were fair-sampling, whether the settings were chosen independently, or whether
any of the loopholes that matter in a real Bell test were closed. Those are
experimental design questions, and this agent does not answer them.
