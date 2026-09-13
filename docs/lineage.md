# Component lineage

A record of where each component originated, so that any later submission can
state precisely what was pre-existing and what was added.

## Originating here (AWS Agents for Humans, 2026-09)

| Component | Module | Version |
| --- | --- | --- |
| `VerdictCard` | `evidence/verdict_card.py` | v1 |
| `EvidenceCertificate` | `evidence/certificate.py` | v1 |
| `ExecutionTrace` | `evidence/execution_trace.py` | v1 |
| Escalation policy | `policy/escalation.py` | v1 |
| Claim-state machine | `policy/claim_states.py` | v1 |
| Ordered verdict rule table | `policy/verdict_rules.py` | v2 |
| CHSH replay engine | `tools/chsh_replay.py` | v2 |
| Root-cause deviation search | `tools/root_cause.py` | v1 |
| Provenance checks PRV-001..006 | `tools/provenance_checker.py` | v1 |

All of the above were written from scratch during the submission period. No
code was carried in from an earlier project.

The current increment also includes the state-gated investigation, bounded
observations, run metadata, local review workbench and certificate-bound
human-intent receipts. The v2 replay/rule semantics distinguish numerical
reproduction from physical interpretation. See `docs/investigation_workflow.md`,
`docs/review_workbench.md` and `docs/chsh_math.md` for the current boundaries.

## Pre-existing, used as a dependency only

| Item | Role |
| --- | --- |
| Strands Agents SDK | Agent framework (`agent/researchops_agent.py`) |
| Amazon Bedrock | Model hosting |
| Amazon Bedrock AgentCore SDK | Optional runtime adapter; not a deployed service |
| pydantic | Schema validation |
| Starlette, Uvicorn | Local HTTP workbench and server |
| SQLite (Python standard library) | Local certificate and human-intent storage |
| httpx | HTTP contract testing |
| pytest, ruff | Test and lint tooling |

## Intended follow-on work

If these components are carried into a later submission, that submission
should record the split explicitly — what arrived from here at v1, and what is
genuinely new. Suggested shape:

```
Carried forward from EvidencePilot v1 (MIT):
  - VerdictCard v1, EvidenceCertificate v1, ExecutionTrace v1
  - EscalationPolicy v1, claim-state machine v1

Added in the later submission:
  - <new routing / sandboxing / counterexample search / certificate v2>
```

Keeping this file current is cheap now and expensive to reconstruct later.
