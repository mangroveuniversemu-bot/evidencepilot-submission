# Stateful investigation: evidence before explanation

## What changed

The narrated POC and operator CLI share the same bounded investigation. A call
to `issue_verdict` plus fluent prose is no longer sufficient for completion.
The agent must collect actual tool results through the legal workflow and
reproduce the independent verification card before the final summary is released.

This is a constrained, conditional workflow, not a freely planning agent or a
trained reinforcement-learning policy. No RL training is required.

## Legal actions

| Current state | Allowed action | Next state |
| --- | --- | --- |
| New | Read selected package | Package read |
| Package read | Check provenance | Replay required, or ready to issue on critical provenance failure |
| Replay required | Recompute from counts | Root cause required on disagreement; otherwise ready to issue |
| Root cause required | Search the declared deviation set | Ready to issue, including unresolved or ambiguous causes |
| Ready to issue | Apply policy and compare the resulting card with the independent baseline | Complete, or failed on mismatch |

A domain replay failure, such as incomplete counts, goes to policy adjudication;
it is not treated as successful scientific validation. A completed investigation
can produce BLOCK, REVIEW, or HUMAN_DECISION as well as ALLOW.

Illegal actions return `action_not_allowed` without executing a tool or advancing
the state. Exceptions stop the investigation. Ordinary changes to input bytes
detected before or after an action invalidate it. Results are copied before being
returned, and a lock serializes concurrent tool requests within one session.

## Authority and traces

- **Independent certificate:** computed before the model runs and kept available
  if the model fails. It retains its own original verification trace.
- **Agent trace:** attempted actions, outcomes (including rejections), before/after
  states, durations, and observation digests for this investigation.
- **Investigation verification trace:** actual read, provenance, replay,
  root-cause and rule-table executions requested in this session. It is separate
  from the independent certificate's trace, not retroactively inserted into it.

The final tool constructs an assessment from these newly collected results,
applies the existing policy and escalation rules, and compares the entire verdict
card with the baseline. Only a matching card releases the baseline summary and
certificate identifier. This intentionally repeats verification work; it does
not improve verification throughput, but makes the agent's work independently
checkable while preserving the offline fallback.

Both runs use the **same verification implementation**. They are separate
executions, not independent scientific algorithms: agreement detects execution
or state divergence, but cannot detect a mathematical mistake shared by both.
Hand-counted counterexamples and definition tests therefore supplement this
baseline comparison. CHSH diagnostics and `physical_interpretation` keep
reproduction separate from physical validation; see [the mathematics](chsh_math.md).

`advisory.status = complete` requires both a completed investigation and nonempty
model prose, without exceeding the model-call budget. It does **not** certify the
truth or quality of that prose: `prose_checked` is false. Certificate authority
does not come from the model. The certificate's SHA-256 field is an integrity
checksum, not an identity-authenticated signature.

`human_attention_required` becomes available after investigation completion.
`human_decision_recorded` remains false: this version asks for human input but
does not persist a person's selection or close the human workflow. HUMAN_DECISION
still carries no recommended option.

## Bounds and entry points

- Five no-argument model tools bound to one host-selected package.
- Six bundled synthetic cases in the public POC API; no caller-supplied path,
  model selection, prompt, credentials, or executable notebook.
- At most 16 tool attempts, plus one overflow log record; 8 model calls and
  1,024 output tokens per call. Elapsed time is checked before model calls at
  120 seconds, not an operating-system hard timeout or a billing cap.
- Each successful model-visible tool observation is at most 16 KiB, with at
  most 64 KiB of accepted observations per investigation. The count uses
  ASCII-escaped JSON bytes including the returned state snapshot, not model
  tokens. Oversized observations are rejected, not silently truncated; the
  session enters `budget_exceeded` and cannot finalize. Its independent
  certificate remains available outside the model conversation.
- `accepted_observation_bytes` counts accepted payloads only. Bounded control
  and rejection messages, SDK envelopes, prompts, repeated context on later
  model calls, and generated prose are not part of this byte allowance. This
  is neither a total input-token cap nor a hard monetary spending limit.
- `python -m app.main agent <trusted-package> --json` uses this same engine and
  returns exit code 2 if narration is unavailable or the investigation incomplete.
  Model selection must be explicit or configured through `EVIDENCEPILOT_MODEL_ID`.
- The path-taking CLI is for a trusted operator, not a public upload endpoint.
  The old unbounded Strands builders have been removed. The prose compatibility
  adapter also refuses to report success on an incomplete investigation.
- The AWS smoke workflow remains manual and uses OIDC credentials. It checks
  structured certificate integrity, card agreement and investigation completion,
  rather than searching for a verdict word in model prose.

Input hash checks are not a sandbox or an atomic filesystem snapshot. This POC
does not claim protection against a concurrent malicious filesystem writer,
arbitrary uploaded programs, or compromised host code. Sessions and their traces
are returned in the response; no durable session database or restart recovery is
implemented. Runtime deployment and live model behavior require separate checks.

## Run configuration records

All narrator results, including `not_configured`, incomplete and model-error
results, include `run_metadata`: a unique run ID, timestamp, baseline certificate
ID/checksum, source and system-prompt SHA-256 fingerprints, installed dependency
versions, configured model/region/temperature, and host-owned limits.

The source fingerprint covers Python files in `agent/`, `app/`, `evidence/`,
`policy/`, and `tools/`, plus `agentcore_app.py` and `pyproject.toml` when present.
It identifies the actual local code, including uncommitted edits; it is not a
Git release identifier. Input files have their own certificate hashes. Private
inputs, `.env`, Git credentials and AWS credentials are never read for metadata.
Account-specific model ARNs are redacted, while their digest remains comparable.

This is a portable configuration record, not authenticated attestation or a
promise of identical model output. A model ID need not pin a provider's exact
weight revision: `resolved_weights_revision` is explicitly null. Reports are
returned to the operator and are not automatically written to a durable store.

## Verification and next step

`tests/integration/test_investigation.py` exercises actual deterministic tools,
all bundled POC routes and additional adversarial fixtures, premature final
requests, changed inputs, mismatched cards, output-copy isolation, tool budgets,
and both the POC narrator and CLI contracts. Scripted SDK stand-ins test protocol
behavior only; they are not evidence of a live model's planning accuracy.
Byte limits are tested at exact boundaries, with Unicode escaping, cumulative
overflow and an oversized final observation. Metadata tests cover source/prompt
changes, baseline binding, unavailable dependencies and identifier redaction.

Before deploying, run the full tests and formatting checks. Next, use one small,
explicitly authorized live Bedrock run to inspect model behavior against this
protocol. Human decision receipts are a separate next increment: bind a person's
choice to the certificate and escalation, validate the offered option, and record
it without rewriting the original certificate. Do not label a case closed until
that receipt is actually implemented and exercised.
