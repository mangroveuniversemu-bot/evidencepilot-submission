# Local review workbench

The browser UI in `app/review_ui.py` connects the existing deterministic
verifier to a separate, durable human-intent record. It uses only the six
allowlisted synthetic cases. It does **not** invoke Bedrock, import a cloud SDK,
execute the selected action, or modify the AgentCore HTTP contract.

## Start

From a source checkout with the bundled `examples/` directory:

```sh
python -m pip install -e ".[dev,ui]"
python -m app.review_ui
```

Open `http://127.0.0.1:8765`. No AWS login is needed. Stop the local server with
Ctrl+C. The default records are stored in `out/reviews/reviews.sqlite3`, under
the project root and excluded by `.gitignore`. Restarting the same command
restores the history. A browser refresh clears an unsaved form, not saved data.
Use `--port 8766 --data-dir /path/to/qa-records` for an isolated rehearsal store.
The server always binds to loopback; there is no public-host option.

## A short walkthrough

1. Select **Maya's review** and click **Run verification**. Inspect `BLOCK`,
   `R-005`, the declared versus replayed values, root cause, tool trace and
   certificate checksum. The visible values are formatted verifier output,
   not UI-computed statistics. The JSON export retains full precision.
2. Select **The human boundary** and verify. The result is `HUMAN_DECISION`;
   none of the options is preselected or recommended. Both alternative
   calculations remain visible; the app does not choose an interpretation.
3. Explicitly choose an option, enter a reviewer alias and a reason, and
   acknowledge that saving records intent only. Click **Save decision record**.
   The confirmation displays the receipt and the unchanged original verdict.
4. Use **Download certificate + decision** to export one JSON bundle. Refresh
   the page, then use **Review history → Open record** to restore it.

`Clean replay` requires no decision. Every other offered decision requires a
nonblank reason, including `OVERRIDE_WITH_JUSTIFICATION`. Selecting that option
does not turn a blocked submission into an accepted or certified claim.

## What a record means

The server retains the original `EvidenceCertificate` before asking for a
choice. A `HumanDecisionInput` supplies only its checksum, an offered option ID,
a self-reported reviewer display name and a reason. The server looks up the
stored certificate, validates the binding and selects the option's original
label/consequence. A caller cannot supply a replacement certificate or verdict.

The separate `HumanDecisionReceipt` captures:

- server UTC time, unique decision ID, certificate ID and checksum;
- escalation ID and selected option, display name and written reason;
- original verdict and claim state, `authority=intent_only`,
  `identity_assurance=self_reported_not_authenticated`, `action_executed=false`;
- an unkeyed SHA-256 checksum over the receipt's canonical JSON.

SQLite transactions and a unique certificate key allow **one receipt per
verification run**. Identical retries return the same receipt; conflicting
submissions return HTTP 409 and never overwrite it. To record changed intent,
start a new verification run; both records remain in the history. This does not
automatically supersede or revoke the earlier record. No update or delete API
is provided. The history shows the latest 100 runs; known older record IDs
remain directly retrievable and exportable.

## Boundaries and limitations

- This is a single-computer POC, **not an authenticated multi-user approval
  system**. Reviewer names are self-reported. Neither checksum is a keyed
  signature, legal authorization, or protection against a local owner changing
  the database and recomputing hashes.
- The original certificate and its stored escalation are preserved. A receipt
  does not execute a rerun, change an input, remove a run, or certify physics.
- The local web boundary checks exact Host and Origin, requires a per-process
  write token, rejects cross-site requests, limits bodies to 16 KiB and serves
  only fixed local assets. It uses no CORS, external fonts, analytics, cookies
  or external requests. The write token is a CSRF defense, **not user identity**.
- Untrusted artifact text and reviewer text are inserted with `textContent`,
  never as HTML. A restrictive content policy forbids external/inline scripts
  and framing. Filesystem access remains limited to known synthetic packages
  and the configured local record store; no upload/path field is exposed.
- Records are not encrypted or backed up automatically. Use a trusted local
  computer. Do not enter credentials or private research into the form, and
  review names/reasons before sharing an exported bundle.
- The UI never claims live model execution. The hosted AgentCore endpoint and
  model tools have **no decision-writing capability**. Hosted authentication,
  durable cloud storage and decision authorization remain out of scope.

## Verification

`tests/unit/test_review_store.py` checks certificate preservation, persistent
receipts, concurrent retries, conflicting saves, tampering, mandatory reasons,
invalid options, and the ALLOW/no-escalation case. `tests/runtime/test_review_ui.py`
checks the HTTP/export contract, request isolation, size limits and rejection of
live-call, arbitrary-path and caller-verdict inputs. The core and UI imports
must not pull in boto3, botocore or Strands.

Browser QA uses a separate store and a clearly labeled QA alias; it is not a
real user decision or live-agent evidence.
