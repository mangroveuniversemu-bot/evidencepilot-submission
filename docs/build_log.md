# Build log

A running record of what was built when, kept for the submission's
"built during the period" requirement.

## 2026-09-01 — Day 1

Repository initialised as a new project. Nothing was carried in from earlier
work; see `docs/ip_boundary.md` and `docs/lineage.md`.

Landed in one vertical slice rather than infrastructure-first:

- `agent/schemas.py` — typed contracts for every artifact, with `EvidenceClass`
  deliberately lacking a `PROOF` member.
- `tools/` — artifact reader with hashing, CHSH replay, provenance checks
  PRV-001..006, root-cause deviation search, finite-verification benchmark,
  report rendering.
- `policy/` — ordered nine-rule verdict table, claim-state machine, escalation
  policy with the "at most one decision" and "no recommendation on a human
  decision" invariants.
- `evidence/` — verdict card, signed certificate with explicit limitations,
  execution trace.
- `agent/researchops_agent.py` — deterministic pipeline plus the Strands
  wiring (Bedrock, five tools, `agent/prompts.py`).
- `app/main.py` — `verify`, `queue`, `benchmark`, `agent`.
- `examples/` — hero case plus four adversarial packages, all synthetic and
  generated with self-consistent hashes by `scripts/build_examples.py`.
- `tests/` — unit, integration, regression, and adversarial suites.
- CI on push and pull request; live Bedrock smoke test on manual dispatch only.

Verified end to end: the hero case blocks with the root cause identified, and
the four adversarial packages land on `ALLOW`, `REVIEW`, `BLOCK`, and
`HUMAN_DECISION` respectively.

Backlog written up in `docs/epics.md` and `scripts/bootstrap_issues.sh`
(milestone plus eight epics, idempotent). The audit behind it found four real
gaps, recorded as open work rather than glossed over: the Bedrock path has
never been executed, there is no way to record a human's decision back into a
certificate, `SECURITY.md` claims a prompt-injection boundary that nothing
tests, and there is no UI.

POC-2 (injection boundary) closed. The tool projections were pulled out of
`build_tools` into strands-free module-level functions so the test can assert
what reaches the model without the agent extra installed and without drifting
from the real tool. 94 tests -> 104.

EPIC-06 closed. Four coverage packages added (`case_h` R-003, `case_i` R-004,
`case_j` R-001, `case_k` R-008) and `test_rule_coverage.py` now fails the build
if any rule loses its package. Writing that test found a gap nobody had listed:
R-008 had never been reachable, because `case_c` fires R-007 first. 104 -> 134
tests.

## 2026-09-12 — finite-sample semantics and bounded observations

Corrected an overstatement in the original CHSH policy: an empirical estimate
above Tsirelson's expectation bound is not automatically physically impossible.
The historical `case_h` now fires R-005 for an actual replay mismatch; `case_i`
fires R-004 for an unsupported expression. R-003 checks the algebraic range,
and new R-010 requires review of reproduced finite-sample boundary cases.
Physical interpretation is separate from reproduction even on ALLOW. Undefined
sigma ratios are omitted rather than computed using an arbitrary tiny divisor.

Added two generated synthetic fixtures and independent hand-counted tests.
Certificates use CHSH/rule tool version 2; old checksum artifacts must be
regenerated, not silently reinterpreted. No finite-sample confidence interval
or loophole-free Bell certification was added.

The stateful investigation rejects oversized observations (16 KiB each, 64 KiB
accepted total) without truncating evidence or falsely finalizing. Public-safe
run records capture source/prompt/dependency/model configuration and limits,
bound to the baseline certificate checksum. They are not authenticated
attestation, durable storage, model-weight pinning or a monetary cap.

233 local tests passed. Isolated regeneration matches all twelve synthetic
packages byte for byte without overwriting the repository. The generator now
creates its output directories when run against a fresh destination.
No live AWS calls, runtime resources, model migration,
fine-tuning or human-decision writeback were performed in this increment.

## 2026-09-13 — live attempt and release preparation

Short-lived CLI/SDK authentication and a read-only STS check succeeded. One
bounded synthetic Maya investigation was attempted through Strands using the
APAC Nova Lite v1 profile. AWS rejected the first request with
`ValidationException`: no agent tool execution or model usage was returned.
The independent certificate retained a valid checksum and matched the baseline
card (`BLOCK`, `R-005`). Missing usage is unknown, not evidence of zero billing.

Fresh control-plane checks found Nova Lite `NOT_AUTHORIZED`, with agreement,
entitlement and region available and the APAC profile active. AgentCore's
applied runtime quota remains zero and the runtime list is empty. AWS Support
received the new diagnostics in the existing case. No live deployment or
successful model run is claimed.

Fixed the transport-error fallback when an SDK exception has `response=None`;
its regression test verifies the private error message is not exposed and the
baseline certificate remains unchanged. All 234 local tests, lint, and formatting
checks pass. See `release_status.md` for the release gate.

## 2026-09-13 — local workbench and human-intent records

Added a loopback-only browser UI with six synthetic cases, deterministic
verdicts, trace inspection, scientific limitations and certificate exports.
The page explicitly separates verification, absent AI advisory and human intent.
It does not call AWS or start a hosted runtime.

Human choices now create a separate SQLite-backed receipt with the original
certificate ID/checksum, an offered option, a mandatory reason, a self-reported
display name and UTC time. Transactional duplicate handling returns the same
receipt on identical retries and rejects conflicting writes. No certificate
is rewritten; no chosen action is executed. Updated old override text that
incorrectly promised an authenticated signature and certificate mutation.

277 tests pass. Added coverage for concurrent saves, certificate/receipt
integrity, no-escalation cases, input bounds, cross-site request rejection and
the HTTP/export contract. Browser rehearsal uses separate QA-only records and
tests literal rendering of adversarial text, persistence and no default choice.
These records do not establish authenticated identity or a successful live agent.

## Notes for later entries

Record, per day: what shipped, what broke, and any decision that would be
expensive to reconstruct later. This file is also the raw material for the
submission's build-story section.
