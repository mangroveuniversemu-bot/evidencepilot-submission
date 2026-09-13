# Verification-only rehearsal

From the repository root in the installed project environment:

```sh
python -m app.demo --case all
python -m app.demo --case human_decision
```

This entry point uses bundled synthetic data only and makes no model calls.
It is a rehearsal aid, not evidence of live Strands or cloud deployment.
The JSON separates deterministic verification, optional AI advisory (not
requested here), and human attention. It does not record or authorize human
decisions. Certificate checksums verify integrity, not signer identity.

For the browser-based workflow with **separate local decision receipts**, run
`python -m app.review_ui` after installing the `ui` extra. See
[the workbench guide](review_workbench.md). This does not add decision recording
to this JSON CLI or to the hosted AgentCore endpoint.

Rehearsal order: `maya` (BLOCK), `clean` (ALLOW), `missing_evidence` (REVIEW),
`human_decision` (HUMAN_DECISION), `stale` (BLOCK), `injection` (BLOCK).
Verdicts come from the existing policy layer, not this presentation entry point.

Before claiming a live demo, separately establish model access and SDK
authentication, invoke a bounded synthetic Strands case, and retain actual
tool-call evidence. Never replace a failed live call with unlabeled simulated
advisory text. AgentCore readiness is a separate deployment check.
