# Release status — 2026-09-13

This is a tested local POC with a cloud access blocker, not a successful live
deployment. All experiment inputs are bundled synthetic fixtures.

## Evidence collected

| Check | Observed result |
| --- | --- |
| Local regression | 277 tests passed; 4 existing dependency deprecation warnings |
| Lint and formatting | Passed |
| Local browser workbench | Six verification-only cases; separate persistent human-intent receipts |
| AWS short-lived SDK authentication | STS identity check succeeded; no long-lived key created |
| One Maya Strands/Bedrock run | First model request rejected with `ValidationException` |
| Agent tool execution / token usage | No tool actions; no usage returned (unknown, not zero) |
| Independent certificate | Integrity valid; card matches baseline; `BLOCK` / `R-005` |
| Nova Lite v1 availability | `NOT_AUTHORIZED`; agreement, entitlement and region `AVAILABLE` |
| APAC Nova Lite profile | `ACTIVE` |
| AgentCore runtime quota / existing runtimes | Applied quota `0`; runtime list empty |

The transport-error handler also preserves the baseline if a network exception
has no response object. None of these results establishes a successful live
agent run. The availability response alone does not identify the underlying
authorization cause; that diagnosis is with AWS Support.

## Run locally

The [judge quickstart](judge_quickstart.md) provides Windows and macOS/Linux
setup, expected outputs, a review-record walkthrough, and the full local test
command. It requires no shared account, AWS login, or live model call.

```bash
python -m pip install -e ".[dev,runtime]"
python -m app.demo --case all
```

That command is **verification-only**, with no model calls. It is suitable for
rehearsing the deterministic behavior, not claiming live-agent success.

For the local visual workflow, install `.[dev,ui]` and run
`python -m app.review_ui`. The workbench records certificate-bound human intent
in local storage, without changing the original evidence or executing the
chosen action. See [the guide](review_workbench.md). It is not a deployed cloud UI.

For the official short-lived `aws login` credential provider, the tested local
SDK also needs its matching crypto extra:

```bash
python -m pip install "boto3[crt]==1.43.89"
```

Use an already authorized profile with Bedrock invocation permission. Do not
repeat login when STS succeeds and the error is model access. Never disable TLS
verification or put credentials, account IDs, session caches, or private CA
files into this repository.

Once access is restored, run one synthetic case using the trusted operator CLI:

```bash
python -m app.main agent examples/maya_case/inputs --model-id apac.amazon.nova-lite-v1:0 --region ap-southeast-2 --json
```

The host permits at most eight model requests, 1,024 output tokens each, and
16 tool attempts. SDK retries are disabled. The 120-second check happens before
each model request; it is not a hard process or monetary cap. Review the actual
usage and any partial execution before retrying.

Require advisory completion, the actual sequence `read_experiment_package` →
`check_provenance` → `replay_chsh` → `search_root_cause` → `issue_verdict`, an
integrity-valid certificate, and a verdict card matching an independent
deterministic run. Both runs share the verification implementation. Model prose
still needs human review. Separate local receipts are implemented in the
workbench; no hosted or model-accessible human-decision writeback is provided.

## Cloud release gate

Do not retry runtime creation while the applied quota is zero. The existing
support case received the fresh diagnostic update; no support-plan upgrade or
unrelated quota request was made.

After AWS restores access:

1. Verify model authorization and complete the bounded live test above.
2. Verify the applied AgentCore quota and the runtime list.
3. Build from the reviewed committed source with the pinned Linux ARM64
   dependencies. Confirm newly added investigation modules are in the ZIP.
4. Upload only the verified ZIP into the existing private POC bucket. Scope
   the runtime role to that exact S3 object key, not a bucket-wide wildcard.
5. Deploy one IAM-authenticated runtime with a 60-second idle timeout and
   600-second maximum lifetime, then verify both non-narrated and narrated
   requests. Do not report an uploaded ZIP as a deployed or healthy runtime.

## Submission gate

The [official rules](https://agentsforhumans.devpost.com/rules), checked on
September 13, specify September 14, 2026 at 17:00 PDT: September 15 at 08:00
in Taiwan. AgentCore and a live demo URL are optional, but a functioning
Strands-based project is required.

Still verify before submission: a reviewed **public** repository with MIT or
Apache license, README and architecture diagram; a public YouTube/Vimeo video
of at most five minutes showing the working project and pitch; the project
description and AWS Builder ID. Repository visibility must not be changed
without owner approval and an IP/secret review. Do not portray an offline
rehearsal as successful live-agent execution.
