# AgentCore POC

`agentcore_app.py` hosts an IAM-authenticated JSON endpoint. Only bundled,
synthetic cases are accepted: `maya`, `clean`, `missing_evidence`,
`human_decision`, `stale`, and `injection`. Client-supplied paths, model IDs,
prompts, credentials, and uploaded experiment data are rejected.

```json
{"case": "maya", "narrate": false}
```

The deterministic certificate is computed and frozen before optional model
narration. It includes an SHA-256 integrity checksum, **not** a keyed digital
signature or an identity guarantee. `narrate: true` uses Strands with five
no-argument tools bound to that same case. Model prose is advisory, even if
the model fails, invents a conclusion, or encounters prompt injection.

## Build and test

Use Python 3.13 for the deployment; local tests also run on Python 3.12.

```bash
pip install -e '.[dev,runtime]' uv
ruff check .
ruff format --check .
pytest -q
python scripts/build_examples.py
git diff --exit-code -- examples/
uv --system-certs pip install --python-version 3.13 \
  --python-platform aarch64-manylinux2014 --target build/agentcore-packages \
  --only-binary :all: -r infra/agentcore/requirements.lock
# Commit reviewed source before building; the ZIP records its Git revision.
python scripts/build_agentcore_zip.py --dependencies build/agentcore-packages
```

The builder packages only tracked source from the six runtime directories,
the entrypoint, the license, and the pinned Linux ARM64 dependencies. It
excludes Git history, local environments, credentials, documents, and build
outputs. Never add private experimental data to the allowlisted examples.
`.gitattributes` and the example generator preserve LF bytes across platforms
so that manifest hashes do not change after a Windows checkout.

## Console deployment

In AgentCore Runtime in `ap-southeast-2`, create `evidencepilot_poc` with:

- Source: S3 / upload `build/evidencepilot-agentcore.zip` into a private bucket
  in the same region.
- Language: Python 3.13; entrypoint: `agentcore_app.py`; compute: microVM.
- Incoming authorization: IAM, not an unauthenticated public endpoint.
- Network: PUBLIC (outbound connectivity); no VPC, NAT gateway, persistent
  filesystem, memory, gateway, or provisioned capacity is needed for this POC.
- Environment: `EVIDENCEPILOT_MODEL_ID=apac.amazon.nova-lite-v1:0`.
- Lifecycle: idle timeout 60 seconds; maximum lifetime 600 seconds.
- Execution role: only this runtime's deployment-object read and logs, plus
  invocation of the selected Bedrock model and APAC inference profile. Do not
  grant administrator access, arbitrary S3 reads, or access-key permissions.

APAC inference can route synthetic inputs outside Sydney within the listed
APAC regions. Verify account eligibility, quota, and model permission with a
real invocation; a visible catalog entry alone does not establish access.

## Validation and cost controls

First invoke `{"case":"maya","narrate":false}`. Expected: `BLOCK`, `R-005`,
and `certificate_integrity_valid=true`. Then invoke the same case with
`narrate:true` and require `advisory.status=complete`, actual recorded tool
calls including `issue_verdict`, and the same deterministic verdict.

The narrator permits at most eight model requests with at most 1,024 output
tokens each. SDK retries are disabled; connect/read timeouts are bounded. The
elapsed-time guard checks before each request and is not a hard process kill
or account-wide spending limit. Parallel invocations have separate budgets.

Check an account cost budget before live calls. Credits can hide net spend:
use pre-credit cost alerts as well as checking credit balance. Budget emails
are delayed notifications, not a hard spending cap. Small S3/log storage
charges can remain after runtime sessions stop. Stop test sessions after use;
remove only this POC's runtime, role, deployment objects, and logs when no
longer needed, after confirming that no required evidence would be lost.

## Deployment evidence

For the latest 2026-09-13 local and live-check results, see
[`docs/release_status.md`](../../docs/release_status.md). The runtime quota is
still zero and the live model request was rejected; no cloud deployment is
claimed by the source release or ZIP build.

Local contract validation: 157 tests passed on 2026-09-07, including the real
SDK HTTP health/invocation routes and Strands tool schemas. No AWS credentials
are required by those tests. **Cloud readiness and live Bedrock success must
be recorded separately after deployment; local success is not live evidence.**

Official references: [direct code deployment](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-code-deploy-python.html),
[runtime permissions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html).
