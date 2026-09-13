# Demo script (target: under 5 minutes)

Everything below runs offline. No AWS credentials are needed for the
deterministic path; the optional narrated segment needs Bedrock access.

## 0:00 — The situation (25s)

> It is 16:17. Maya has a quantum-device review at 17:00. A collaborator has
> submitted a run claiming the CHSH bound is violated: S = 2.61. The notebook
> that produced it was not submitted. Checking this by hand means parsing raw
> counts, applying the lab's measurement convention, recomputing four
> correlations, propagating the uncertainty, and confirming the artifacts
> describe the run they claim to. This is our demonstration scenario, not a
> measured claim about the time saved.

## 0:25 — Run it (35s)

```bash
python -m app.main --deadline-note "Device review starts in 43 minutes (17:00)." \
    verify examples/maya_case/inputs
```

Let the verdict card render. Do not read it aloud line by line; point at three
things:

- **Submitted 2.6100, replayed 1.9625 ± 0.0104.** Does not pass the approximate
  classical-bound screen. Physical interpretation remains unestablished.
- **The root cause, named.** The registered channel correction for `BLK-02`
  was declared in the convention file and not applied by the analysis.
- **One decision**, with the consequence of each option spelled out.

## 1:00 — Why this is the hard part (45s)

Show `docs/chsh_math.md`, the worked table.

> Dropping one documented channel correction flips the sign of one correlation
> and turns 1.9625 into 2.6125, which rounds to exactly the 2.61 that was
> submitted. The agent does not just report a disagreement — it reproduces the
> submitted number under a specific wrong convention, which is what makes the
> finding actionable.

Then the honest detail:

> Two different mistakes land on 2.6125. Only one also reproduces the
> per-pair correlations in the submission, and that is how the agent picks.
> Withhold those correlations and it reports the ambiguity instead of
> guessing — there is a test for that.

## 1:45 — The other three outcomes (60s)

```bash
python -m app.main queue examples/review_queue/queue.json
```

Four packages, four different outcomes:

| Package | Verdict | Why |
| --- | --- | --- |
| `case_e_clean_pass` | `ALLOW` | reproduces, provenance complete |
| `case_c_missing_evidence` | `REVIEW` | arithmetic fine, convention unregistered |
| `case_d_human_decision` | `HUMAN_DECISION` | conclusion flips on a flagged sub-run |
| `maya_case` | `BLOCK` | not reproduced, root cause identified |

Land on `case_d`:

> Both analyses are arithmetically correct. Including the flagged sub-run
> gives 2.35 and passes the approximate screen. Excluding it gives 1.98 and
> does not. Neither is a certified Bell violation. The choice depends on
> instrument behaviour, not just computation — so the agent
> presents both numbers and **deliberately makes no recommendation**. There is
> a test asserting it never does.

## 2:45 — The refusal (35s)

```bash
python -m app.main benchmark collatz --limit 1000000
```

> A million integers checked, no counterexample. The certificate says the
> claim **remains open**, and carries the limitation verbatim:
> `FINITE VERIFICATION PASS != PROOF`. The evidence-class enum has no `PROOF`
> member and the certificate issuer raises if anyone tries to write one in.
> An agent that knows when it is not allowed to promote evidence into a
> theorem is the whole point.

## 3:20 — How it is built (50s)

Show `docs/architecture.svg`.

> Four layers. The Strands agent sequences tools and writes the explanation.
> It never computes a number and never picks the verdict — those come from
> deterministic Python and an ordered rule table that run with no model and no
> network. Which is why the deterministic path and the Bedrock path produce
> identical certificate verdicts by construction. Live model tool use and
> explanation quality require a separate test; local replay does not establish them.

Optional, if Bedrock credentials are configured:

```bash
python -m app.main agent examples/maya_case/inputs
```

## 4:10 — Evidence (30s)

```bash
python -m pytest -q          # 277 tests with dev, ui and runtime extras (2026-09-13)
```

> Unit, integration, regression, adversarial, runtime and UI contracts. Twelve
> synthetic packages cover every verdict rule, with invariants that fail the build if the
> agent ever recommends its way through a human decision, lets a finite search
> read as a proof, or lets an injected instruction touch a certificate.
> These are local tests, not evidence of a successful live Bedrock run.

## 4:40 — Close (20s)

> The verifier replayed the submitted artifacts, identified the missing channel
> correction, and asked Maya one question. That is the intended product:
> routine checking completes, and the remaining human decision is explicit.
> We have not yet measured time saved against manual review.
