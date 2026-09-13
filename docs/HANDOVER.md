# Handover

Implementation and cloud-check status updated 2026-09-13. Read this first if you are picking the project up.

## Where the code is

The canonical submission source is:

```
repo    github.com/mangroveuniversemu-bot/evidencepilot-submission
branch  main
```

Start from this repository for submission changes:

```bash
git clone https://github.com/mangroveuniversemu-bot/evidencepilot-submission
cd evidencepilot-submission
```

This repository starts with a reviewed source snapshot; original development
history remains private. Its first commit dates the packaging, not the start
of the project. No old Git history, credentials, local decision records or
private research were imported. Migration-only bootstrap helpers are omitted.
Use privacy attribution and import reviewed file changes, not commits from old
history. See `docs/repository_workflow.md`.
The restricted AgentCore JSON POC, build process, cost controls, and validation
criteria are documented in `infra/agentcore/README.md`. A successful local
contract test must not be reported as a successful live deployment.

## Current local increment

The narrated POC and operator CLI use a state-gated investigation, bounded tool
observations, and public-safe run configuration fingerprints. The final tool
must rederive the model-independent baseline card before releasing its summary.
Both executions share verification code; matching them is not an independent
scientific validation. See `docs/investigation_workflow.md`.

CHSH rule version 2 separates numerical replay from physical interpretation.
R-004 checks the supported definition, R-003 checks the algebraic range, and
R-010 reviews finite-sample boundary cases. Old sample-above-Tsirelson BLOCK
semantics are superseded. New certificate fields change checksum serialization;
regenerate old artifacts from inputs rather than silently upgrading them.

Local regression: 277 tests passed, including hand-computed small-sample
counterexamples, observation-limit failures, and metadata redaction. No live
Bedrock call or deployment is established by those tests. Existing deployment
artifacts must be rebuilt from a verified release before claiming these changes
are deployed. The loopback-only workbench now records separate, persistent
human-intent receipts; it never changes a certificate or executes the choice.
See `docs/review_workbench.md`. Hosted decision writeback is not implemented.

## Original bootstrap inventory (historical, not a current file count)

The original handover listed 117 tracked files. The table below predates the
POC runtime, offline rehearsal and stateful-investigation additions.

| Area | Files | Contents |
| --- | ---: | --- |
| `examples/` | 52 | 10 experiment packages, all synthetic, all generated |
| `tests/` | 15 | unit · integration · regression · adversarial |
| root | 10 | README, LICENSE, SECURITY, CONTRIBUTING, AGENTS, NOTICE, Makefile, pyproject, .gitignore, .env.example |
| `docs/` | 8 | architecture (+ SVG), CHSH maths, IP boundary, lineage, demo script, build log, epics, this file |
| `tools/` | 7 | artifact reader, CHSH replay, provenance, root cause, benchmark, reports |
| `agent/` | 5 | schemas, state, prompts, Strands wiring + deterministic pipeline |
| `.github/` | 5 | CI, AWS smoke test, issue and PR templates |
| `policy/` | 4 | claim states, verdict rules, escalation |
| `evidence/` | 4 | verdict card, certificate, execution trace |
| `scripts/` | 3 | example generator, repo bootstrap, issue bootstrap |
| `infra/` | 2 | AgentCore and AWS runtime notes |
| `app/` | 2 | CLI |

Files you will touch most:

- `tools/chsh_replay.py` — the arithmetic everything rests on
- `policy/verdict_rules.py` — the ten ordered rules; ordering *is* the policy
- `scripts/build_examples.py` — the only place example data is authored
- `docs/epics.md` — what is done and what is open

## Language

Everything in the repository is **English**: code, comments, docs, commit
messages, example data. The submission is judged in English, and mixing
languages inside a public repository reads badly. Keep it that way.
Discussion outside the repository can be in any language.

## What runs

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ui,runtime]"

make test      # 277 local tests with all extras (2026-09-13)
make lint      # ruff check + ruff format --check
make demo      # the hero case
make queue     # four outcomes side by side
make collatz   # the refusal
make examples  # regenerate example data; must produce no diff
python -m app.review_ui  # loopback-only browser workbench; no model calls
```

No AWS credentials are needed for any of the above, and CI makes no AWS calls.
For setup without Make or shell activation, see `docs/judge_quickstart.md`.
A step in CI asserts the verification core never imports boto3, botocore or
strands, so the deterministic path cannot quietly acquire a cloud dependency.

## Where things stand

Landed and tested: the CHSH replay engine, provenance checks PRV-001..006, the
root-cause deviation search, the ten-rule verdict table, the claim-state
machine, the escalation policy, integrity-checksummed certificates, execution
traces, the CLI, twelve synthetic experiment packages, and 277 local tests.

Every verdict rule R-001..R-010 fires from a synthetic package, asserted by
`tests/adversarial/test_rule_coverage.py`. Adding a rule without a package that
reaches it turns the build red.

Open work is tracked in `docs/epics.md`. The four things that actually matter:

1. **Successful live execution remains blocked.** The first Strands/Bedrock
   request was attempted on September 13 and rejected with `ValidationException`.
   Fresh Nova Lite availability reports `NOT_AUTHORIZED`; no agent tool action
   or model usage was returned. See `docs/release_status.md` for the evidence.
2. **Local human decisions are recorded separately.** `app/review_store.py`
   binds self-reported reviewer intent to the original certificate, with
   mandatory reasons, persistent history and safe duplicate handling. It is not
   authenticated approval and does not execute the action. EPIC-05 local scope is met.
3. **The visual workbench is verification-only.** `app/review_ui.py` serves six
   cases, traces, certificate/receipt exports and history. Its loopback server
   is not a deployed web service. `app/demo.py` remains a read-only JSON rehearsal.
4. **AgentCore is undeployed.** Notes and IAM policy exist; nothing is hosted.
   EPIC-07.

## Next action

Short-lived SDK authentication has succeeded; do not restart login unless an
actual expiry or invalid-credential error occurs. AWS Support has received the
fresh model-authorization and zero-runtime-quota diagnostics. After access is
restored, rerun one bounded synthetic case and require actual tool completion.
Keep the verification-only fallback honestly labelled. Use the local workbench
to rehearse the evidence-to-human-intent flow; do not imply that its receipts
authenticate reviewers or are part of the hosted AgentCore runtime.

AWS promotional credits close before the submission deadline. Check both dates
against the official rules before planning the final week.

## Conventions worth knowing before you edit

- **No model output becomes a number.** Anything in a `VerdictCard` or
  `EvidenceCertificate` is computed in `tools/` and decided in `policy/`.
  The public POC tools take no arguments and close over a host-selected package.
  They execute only legal state transitions, so there is no model parameter
  through which a replacement number, path or verdict could arrive. The path-
  taking CLI is for a trusted operator, not public uploads.
- **`EvidenceClass` has no `PROOF` member.** Do not add one.
- **A `HUMAN_DECISION` never carries a recommendation**, and a claim produces
  at most one escalation. Both are tested.
- **Example data is generated, never hand-edited.** Author it in
  `scripts/build_examples.py` and run `make examples`; CI diffs the result.
- **Adversarial tests assert two halves.** A test that only checks "the verdict
  did not change" can pass while proving nothing. See
  `tests/adversarial/test_prompt_injection.py` for the pattern: first prove the
  payload reaches the model, then prove it changed nothing.
