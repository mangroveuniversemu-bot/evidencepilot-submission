# EvidencePilot

**An autonomous verification agent for research workflows. It does the checking, and asks you exactly one question.**

[Judge quickstart](docs/judge_quickstart.md) · [Architecture](docs/architecture.md) · [The maths](docs/chsh_math.md) · [Demo script](docs/demo_script.md) · [Scope & IP](docs/ip_boundary.md)

Built for the AWS **Agents for Humans** hackathon with the **Strands Agents SDK** and **Amazon Bedrock**.

**Release status (2026-09-13):** 277 local tests pass. The first live Bedrock
request was rejected; no successful live agent run or AgentCore deployment is
claimed. See [current evidence and release steps](docs/release_status.md).

This is the submission source snapshot. See [repository workflow and privacy](docs/repository_workflow.md)
before contributing or importing changes from another checkout.

## Review workbench

New to the repository? Start with the [Windows and macOS/Linux instructions](docs/judge_quickstart.md).

```bash
python -m pip install -e ".[dev,ui]"
python -m app.review_ui
```

Open `http://127.0.0.1:8765` to inspect six synthetic cases, execution traces,
certificates and scientific limitations. Select a human action and record a
reason, self-reported reviewer name and UTC time. Saved decisions can be
reopened or exported with the **unchanged** original certificate. No action is
executed and no blocked verdict becomes an approval.

This workbench is explicitly **verification-only**: no AWS login, model call,
or cloud deployment. Records stay in git-ignored local storage. See the
[workbench guide and trust boundaries](docs/review_workbench.md).

---

## The problem

It is 16:17. Maya has a quantum-device review at 17:00.

A collaborator has submitted a run claiming a violation of the CHSH inequality:
**S = 2.61**, comfortably past the classical bound of 2. The notebook that
produced it was not submitted.

Verifying that number by hand means parsing the raw coincidence counts,
applying the lab's registered measurement convention, recomputing four
correlation values, combining them, propagating the uncertainty, and confirming
the artifacts actually describe the run they claim to. Every step is
mechanical under the declared assumptions. The forty-three-minute deadline is
demo narrative, not a measured manual-work baseline.

## What the agent does

```bash
python -m app.main verify examples/maya_case/inputs
```

```
==========================================================================
  VERDICT: CLAIM NOT REPRODUCED
==========================================================================
  Claim       CLM-2026-0831-CHSH
  Decision    BLOCK   (rule R-005)
  Claim state NOT_REPRODUCED
  Evidence    STATISTICAL_REPLAY
  Physics     NOT_ESTABLISHED

  Submitted   S = 2.6100
  Replayed    S = 1.9625 +/- 0.0104 (plug-in SE)
  Screen      -3.6 sigma vs classical bound 2; not a certified Bell test
  Difference  +0.6475 = 62.4 plug-in sigma

    E(a,b)   = +0.7625
    E(a,b')  = +0.3250
    E(a',b)  = +0.7625
    E(a',b') = +0.7625

  ROOT CAUSE
    Registered channel correction for BLK-02 (alice=standard,
    bob=inverted) was declared but not applied.

--------------------------------------------------------------------------
  ONE DECISION REQUIRED
--------------------------------------------------------------------------
  [*] RERUN_UNDER_REGISTERED_CONVENTION
        -> The corrected statistic is S = 1.9625 +/- 0.0104, which
           does not pass the approximate classical-bound screen.
           This does not certify a physical interpretation.
  [ ] EXCLUDE_RUN
  [ ] OVERRIDE_WITH_JUSTIFICATION

  Device review starts in 43 minutes (17:00).
==========================================================================
```

The answer is not *"quantum entanglement is real."* It is: **this specific
claim does not reproduce, here is the exact analysis step responsible, and
here is the one decision only you can make.**

## Why the root cause matters

"The numbers disagree" leaves the work with the scientist. So the agent
replays a declared set of deviations from the registered convention and finds
which one reproduces the submitted number:

| pair | E, registered | E, correction dropped |
| --- | ---: | ---: |
| `a_b` | +0.7625 | +0.7625 |
| `a_bp` | **+0.3250** | **−0.3250** |
| `ap_b` | +0.7625 | +0.7625 |
| `ap_bp` | +0.7625 | +0.7625 |
| **S** | **1.9625** | **2.6125** → rounds to the submitted **2.61** |

One documented channel correction, declared in the convention file and not
applied by the analysis, changes whether the approximate classical-bound screen
passes. Neither outcome is a certified physical Bell violation.

And the agent is careful about it: **two** different mistakes land on 2.6125.
Only one also reproduces the per-pair correlations in the submission, and that
is how it picks. Withhold those correlations and it reports the ambiguity
rather than guessing — pinned by
[`tests/unit/test_root_cause.py`](tests/unit/test_root_cause.py).

## Four outcomes, not one

```bash
python -m app.main queue examples/review_queue/queue.json
```

| Package | Verdict | Why |
| --- | --- | --- |
| `case_e_clean_pass` | `ALLOW` | Replays within tolerance, provenance complete. Physical interpretation remains unestablished. |
| `case_c_missing_evidence` | `REVIEW` | Arithmetic is right; the convention is unregistered. Reproduction is not certification. |
| `case_d_human_decision` | `HUMAN_DECISION` | Including a flagged sub-run gives 2.35; excluding it gives 1.98. Both are correct. **The agent makes no recommendation.** |
| `maya_case` | `BLOCK` | Not reproduced; root cause identified. |
| `case_a_stale_artifact` | `BLOCK` | The claim was computed against a different dataset. Stops *before* replaying, because replaying the wrong data gives a confident wrong answer. |
| `case_l_finite_sample_boundary` | `REVIEW` | Four synthetic single-shot samples give S = 4. The number reproduces; crossing an expectation bound alone is not impossible physics. |

Numerical reproduction and physical interpretation are separate fields. The
verifier does not establish fair sampling, close Bell-test loopholes, or provide
a rigorous finite-sample confidence interval. See [the scope of the mathematics](docs/chsh_math.md).

## The refusal

```bash
python -m app.main benchmark collatz --limit 1000000
```

```
  VERDICT: CLAIM REMAINS OPEN
  No counterexample to the Collatz conjecture for n <= 1,000,000.

  ! FINITE VERIFICATION PASS != PROOF
  ! Exactly 1,000,000 cases were checked. Every integer above that limit is
    untested. A universal statement about all integers does not follow from
    any finite search, however large.
```

`EvidenceClass` has no `PROOF` member, `policy/claim_states.py` refuses to put
a universal claim in state `REPRODUCED` on finite evidence, and the certificate
issuer raises if anyone writes promotion language into one. An agent that knows
when it is *not allowed* to turn evidence into a theorem is the point, not a
footnote.

## How it is built

![Architecture](docs/architecture.svg)

Four layers, and they do not blend:

| Layer | Directory | Does | Never does |
| --- | --- | --- | --- |
| **Agent** | `agent/` | Sequences tools, writes the explanation | Computes a number, picks the verdict |
| **Tools** | `tools/` | Reads artifacts, hashes, computes | Applies policy |
| **Policy** | `policy/` | Decides verdict, claim state, escalation | Computes a physical quantity |
| **Evidence** | `evidence/` | Assembles, checksums, refuses overstatement | Changes a verdict |

The Strands agent orchestrates and narrates. Every number and every verdict
comes from deterministic Python and an ordered rule table that run with **no
model, no credentials, and no network** — so `verify` and `agent` produce
identical verdicts, CI is free and fast, and the adversarial suite is
meaningful.

## Quickstart

```bash
git clone https://github.com/mangroveuniversemu-bot/evidencepilot-submission.git
cd evidencepilot-submission
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

make demo       # the hero case
make queue      # all four outcomes
make collatz    # the refusal
make test       # core tests; optional UI/runtime tests need their extras
```

To run the full 277-test suite recorded on 2026-09-13, install the optional
contracts too: `pip install -e ".[dev,ui,runtime]"`, then run `make test`.
These tests do not call AWS or establish a successful live model run.

Optional — the narrated path, which needs AWS credentials with Bedrock access:

```bash
pip install -e ".[agent]"
python -m app.main agent examples/maya_case/inputs
```

## Evidence

```
277 local tests     unit · integration · regression · adversarial · runtime + UI contracts
12 packages         every verdict rule R-001..R-010 fires from a synthetic package
Coverage includes   stale artifact · disagreement · missing evidence · consequential
                    choice · invalid definition · incomplete acquisition · finite samples
0 AWS calls in CI   the verification core has no cloud dependency
```

Invariants that fail the build if violated:

- A claim produces **at most one** escalation.
- A `HUMAN_DECISION` **never** carries a recommendation.
- Finite verification can refute a universal claim; it can never confirm one.
- A certificate's SHA-256 checksum covers its verdict, so an unchanged checksum
  detects a modified card. This is not an identity-authenticated signature.
- A prompt-injection payload in a submitted artifact reaches the model and
  changes **nothing** in the certificate. Both halves are asserted, because
  either alone would mislead — see `SECURITY.md`.
- Every rule in the table is reachable from a package. Add a rule without one
  and the build goes red.

The narrated POC now requires a completed, state-gated tool investigation.
Per-observation and cumulative byte limits stop oversized tool results without
silently truncating evidence. Run metadata records source, prompt, dependencies
and host-owned limits. These are local contract tests, not proof of successful
live Bedrock execution; see [workflow boundaries](docs/investigation_workflow.md).

## Repository map

```
agent/      schemas, state, prompts, Strands wiring + deterministic pipeline
tools/      artifact reader, CHSH replay, provenance, root cause, benchmark, reports
policy/     claim states, ordered verdict rules, escalation policy
evidence/   verdict card, checksummed certificate, execution trace
app/        CLI, local review workbench, certificate-bound decision receipts
examples/   hero case + adversarial packages (all synthetic)
tests/      unit · integration · regression · adversarial
docs/       architecture, CHSH maths, IP boundary, lineage, demo script, build log
infra/      AgentCore and AWS deployment notes
scripts/    example generator, repository bootstrap
```

## Data and scope

Every dataset here is **synthetic**, generated by
[`scripts/build_examples.py`](scripts/build_examples.py), and constructed so
that each package exhibits one documented failure mode exactly. No measured
data, no unpublished research, and no third-party data appears in this
repository. See [`docs/ip_boundary.md`](docs/ip_boundary.md).

The Bell/CHSH scenario is drawn from textbook material and the publicly
described experiments recognised by the 2022 Nobel Prize in Physics
(Aspect, Clauser, Zeilinger).

## Licence

MIT — see [`LICENSE`](LICENSE).
