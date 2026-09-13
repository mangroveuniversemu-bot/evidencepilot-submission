# Judge quickstart

EvidencePilot checks synthetic research artifacts, explains a reproducibility
failure, and preserves a human's stated next step separately from the evidence.
The local review workbench is **verification-only**: it does not invoke a model,
require AWS credentials, or execute the selected action.

As of September 13, 2026, 277 local tests pass with all optional test dependencies.
The attempted live Strands/Bedrock run was rejected at the first model request;
no successful live-agent run or AgentCore deployment is claimed. See
[release status](release_status.md) for the separate live-execution gate.

## 1. Get the source

Use Python 3.11 or newer and a source checkout containing `examples/` and
`app/static/`. Internet access is needed to download Python dependencies, not to
run the deterministic cases. No GPU or cloud account is needed for this guide.

Clone this repository or use GitHub's **Code → Download ZIP** and extract it.
Open a terminal in the directory containing `pyproject.toml`.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,ui]"
.\.venv\Scripts\python.exe -m app.review_ui
```

These commands use the environment's Python directly; no activation script,
administrator permission or PowerShell execution-policy change is required.

### macOS or Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,ui]"
.venv/bin/python -m app.review_ui
```

Open `http://127.0.0.1:8765`. Keep the terminal open while using the workbench.
If that port is already in use, add `--port 8766` and open that port instead.
The server binds only to this computer. Do not expose it through a public tunnel.

## 2. Inspect the evidence, then record intent

1. Select **Maya's review**, then **Run verification**. Expect `BLOCK`, rule
   `R-005`, submitted S = 2.6100 and replayed S = 1.9625. Inspect the missing
   channel correction, trace and certificate. Physical interpretation remains
   unestablished; a reproduced number is not a certified Bell test.
2. Select **The human boundary** and verify. Expect `HUMAN_DECISION`, two valid
   alternative calculations, and **no preselected or recommended option**.
3. For a clearly labelled synthetic rehearsal, choose an offered option, use
   a reviewer alias such as `Judge demo`, enter a reason, and acknowledge that
   this records intent only. Click **Save decision record**.
4. Use **Download certificate + decision**, refresh, then reopen the entry
   from **Review history**. The original certificate and verdict are unchanged.

The alias is self-reported, not an authenticated identity. A saved choice does
not rerun an experiment, authorize a blocked claim, or change the verdict.
Checksums detect modifications relative to the original checksum; they are not
identity-authenticated signatures.

The six workbench cases have these expected verdicts:

| Case | Verdict |
| --- | --- |
| Maya's review | `BLOCK` |
| Clean replay | `ALLOW` |
| Missing provenance | `REVIEW` |
| The human boundary | `HUMAN_DECISION` |
| Stale artifact | `BLOCK` |
| Untrusted instructions | `BLOCK` |

The last case establishes deterministic artifact handling, not that a live
model resisted an injection. Live model behavior needs its own evidence.

## 3. Reproduce the local checks

Stop the server with Ctrl+C, or use a second terminal in the source directory.
For the full test suite, install the optional runtime contract dependencies too.
This installs SDK packages but does not request AWS access or invoke a model.

Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,ui,runtime]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m app.demo --case all
```

macOS/Linux:

```sh
.venv/bin/python -m pip install -e ".[dev,ui,runtime]"
.venv/bin/python -m pytest -q
.venv/bin/python -m app.demo --case all
```

The recorded result is 277 passing tests and four existing dependency
deprecation warnings. The JSON rehearsal returns six integrity-valid
certificates, `mode=verification_only`, and `live_model_tested=false`.
This read-only CLI does not create a human decision record.

## Data, costs and boundaries

- All bundled experiment data is synthetic; no measured or unpublished research
  is needed. See [scope and IP](ip_boundary.md) and [component lineage](lineage.md).
- Workbench records stay in `out/reviews/reviews.sqlite3`, excluded from Git.
  Stop/restart preserves them. Use `--data-dir out/judge-rehearsal` to keep a
  separate local rehearsal store. Do not enter private research or credentials;
  inspect aliases and reasons before sharing an exported record.
- Nothing in this quickstart makes an AWS inference request or creates a cloud
  resource. The separate live-agent instructions can incur charges and require
  the operator's own permitted credentials; never share root login details,
  access keys or session tokens in the repository or submission.
- The local UI and optional AgentCore adapter are different entry points. An
  AgentCore ZIP or successful local HTTP test does not establish deployment.

For the implementation, start with the [architecture](architecture.md),
[investigation workflow](investigation_workflow.md), [workbench trust boundaries](review_workbench.md),
and [security model](../SECURITY.md). The license is [MIT](../LICENSE).
