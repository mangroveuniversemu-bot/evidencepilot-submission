# Contributing

## Ground rules

1. **No model output becomes a number.** Anything that lands in a
   `VerdictCard` or an `EvidenceCertificate` is computed by deterministic
   Python in `tools/` and decided by the rule table in `policy/`.
2. **Every new verdict path needs an adversarial test.** A rule that has only
   ever been exercised by a passing case is untested.
3. **Never widen `EvidenceClass`.** In particular, `PROOF` is not a member and
   must not become one. See `policy/claim_states.py`.
4. **Example data stays synthetic.** Add new cases to
   `scripts/build_examples.py` and regenerate with `make examples` so hashes
   stay self-consistent.

## Workflow

Trunk-based. Branch from `main` as `feat/*`, `fix/*`, or `docs/*`, open a pull
request even when working alone, and merge once CI is green. The pull request
history is the development record for this project.

## Local checks

```bash
make install
make lint
make test
make demo
```

CI runs the same commands. No AWS credentials are required for any of them.
