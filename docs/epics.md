# Submission backlog

Milestone: **AWS Agents for Humans — Submission v1.0**, due **2026-09-14 17:00 PT**.
AWS promotional credits close earlier, **2026-09-11 12:00 PT**.

Run `scripts/bootstrap_issues.sh` once the repository exists to create the
milestone and these eight epics as GitHub issues. The script is idempotent.

Each epic below records what has already landed and what is genuinely open.
The remaining release work is concentrated in successful live execution,
optional cloud hosting, and the submission package. Local review UI and
human-intent recording are now implemented; hosted approval is not.

---

## EPIC-01 — Strands agent core

**Outcome:** the narrated path produces the same verdict as the deterministic
path, against real Bedrock.

Landed: Strands wiring against SDK v1.54 (`agent/researchops_agent.py`), five
tools, system prompt with the no-numbers rule (`agent/prompts.py`), a manual
smoke-test workflow that asserts the narrated output reports the deterministic
verdict.

Open:
- [ ] Complete a successful Bedrock run. The first live Strands request on 2026-09-13 failed with `ValidationException`; Nova Lite availability is `NOT_AUTHORIZED`. SDK authentication works, but the live tool-calling loop remains unproven. See `release_status.md`.
- [ ] Confirm the model calls the tools in a sensible order and does not invent numbers when a tool result is missing a field.
- [ ] Tune the system prompt against the observed transcript; keep the final answer under 200 words.
- [ ] Dispatch `.github/workflows/aws-smoke-test.yml` and get it green.

**Done when:** the smoke-test workflow passes on a real Bedrock call.

---

## EPIC-02 — Maya end-to-end scenario

**Outcome:** the hero case runs start to finish and its numbers are frozen.

Landed: synthetic package with a documented inverted channel map on `BLK-02`,
replay giving S = 1.9625 ± 0.0104 against a submitted 2.61, root cause
identified and disambiguated from the sign-flip candidate, frozen expectations
in `examples/maya_case/expected/verdict.json`, regression suite.

Open:
- [ ] Nothing blocking. Revisit only if the demo script changes.

**Done when:** already met.

---

## EPIC-03 — Tool execution

**Outcome:** every number in a certificate comes from deterministic Python.

Landed: `artifact_reader` (parse + hash), `chsh_replay` (convention correction
→ E → S → σ, signs read from the convention file), `provenance_checker`
(PRV-001..006), `root_cause` (declared deviation search), `benchmark_runner`
(finite verification), `report_generator`. CI asserts the verification core
never imports boto3, botocore or strands.

Open:
- [ ] Nothing blocking.

**Done when:** already met.

---

## EPIC-04 — Verdict and certificate

**Outcome:** a signed, re-checkable record that states its own limits.

Implemented locally: ten ordered verdict rules, separate replay/physical-
interpretation states, an integrity-checksummed certificate with
`assert_no_theorem_promotion`, and execution traces with per-step digests.
The checksum is not authenticated signing. See `docs/chsh_math.md` for version-2
finite-sample semantics and certificate compatibility.

Open:
- [ ] Nothing blocking.

**Done when:** already met.

---

## EPIC-05 — Human escalation

**Outcome:** the human's decision is recorded, not just requested.

Landed: at most one escalation per claim, each option states its consequence,
a `HUMAN_DECISION` carries no recommendation, invariants enforced in code and
tested.

Implemented local scope (2026-09-13):
- [x] The browser workbench persists a separate receipt containing the exact certificate ID/checksum, selected option, self-reported name, reason and server UTC time.
- [x] Every choice requires a reason, including `OVERRIDE_WITH_JUSTIFICATION`. The original verdict remains unchanged; recording intent executes no action and authorizes no claim.
- [x] Tests cover binding, concurrent identical retries, conflicting writes, tampering and restart persistence. There is no preselected option; HUMAN_DECISION has no recommendation.

**Local done condition met:** a verification can be followed by an exportable,
certificate-bound human-intent receipt. This supersedes the original proposal
for a second "signed certificate": checksums are not authenticated signatures.
Identity-verified hosted approval remains out of scope. See `review_workbench.md`.

---

## EPIC-06 — Failure and adversarial tests

**Outcome:** the failure classes are covered, including the one the security
policy claims.

Landed: five canonical scenarios (`ALLOW` / `REVIEW` / `BLOCK` /
`HUMAN_DECISION` / finite verification), four failure classes, invariant tests
for single-escalation and no-theorem-promotion.

Open:
- [x] Prompt-injection boundary. `case_g_prompt_injection` plus `tests/adversarial/test_prompt_injection.py` (10 tests). Payload lives in the identifiers, since `manifest.notes`, `manifest.operator`, `claim.conclusion` and `claim.submitted_by` are returned by no tool. Asserts both that the payload reaches the model and that the verdict, numbers, root cause and normalised certificate signature are unchanged. Falsified against the clean package to confirm it is not vacuous. **Only covers the deterministic path — what a model writes under injection needs EPIC-01.**
- [x] Corrected boundary semantics (2026-09-12). Historical `case_h_unphysical_claim` is a replay mismatch (R-005); `case_i_unphysical_convention` is an unsupported all-positive expression (R-004), not a physical impossibility. Names remain for traceability. New `case_l_finite_sample_boundary` gives reproducible empirical S=4 (R-010 REVIEW), while `case_m_algebraic_claim` claims S=4.2 (R-003 BLOCK).
- [x] Missing acquisition block. `case_j_incomplete_counts` (R-001) — the convention declares `ap_bp` and the counts file has no rows for it.
- [x] `case_k_missing_environment` (R-008). Not in the original plan: writing the coverage test showed R-008 had never been reachable, because `case_c` fires R-007 first. Registered convention, numbers agree, no environment lock.
- [x] `tests/adversarial/test_rule_coverage.py` asserts every rule in the table fires from some package, and that the R-000 fallback stays unreachable. Falsified by hiding a fixture.

**Local coverage:** 277 tests; R-001..R-010 all reachable from synthetic packages.
Stateful SDK stand-ins do not establish live model robustness or planning quality.

---

## EPIC-07 — AgentCore deployment

**Outcome:** the narrated demo runs somewhere other than a laptop.

Landed: deployment notes, minimum IAM policy, cost posture, OIDC-based CI
credentials (no long-lived keys).

Open:
- [ ] Request Bedrock model access in the target region.
- [ ] Create the execution role; set `AWS_ROLE_ARN` as a repository secret.
- [ ] Deploy the agent to AgentCore and record what actually worked in `infra/agentcore/README.md`.
- [ ] Claim AWS promotional credits **before 2026-09-11 12:00 PT**.

**Done when:** a deployed endpoint returns the same verdict as the local run.

---

## EPIC-08 — Submission package

**Outcome:** a judge can understand the project in five minutes.

Landed: judge-facing README, architecture diagram, CHSH maths write-up, demo
script, IP boundary, lineage, build log, MIT licence, issue and PR templates.

Open:
- [x] Build the local UI: `app/review_ui.py` and `app/static/` provide the verification workbench, persistent decision receipts and JSON export. The screen labels the absence of live model execution explicitly.
- [ ] Record the demo video, under five minutes, following `docs/demo_script.md`.
- [ ] Make the repository public.
- [ ] Tag `v0.9.0-rc1`, then `v1.0.0` after a final regression run.
- [ ] Submit on Devpost before **2026-09-14 17:00 PT**.

**Done when:** the submission is filed and the public repository builds green from a clean clone.
