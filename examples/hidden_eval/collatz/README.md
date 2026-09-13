# Hidden evaluation case — the Collatz conjecture

This case exists to test one product rule, not to advance number theory.

```bash
python -m app.main benchmark collatz --limit 1000000
```

Every trajectory below the limit reaches 1. The interesting part is what the
agent is **not** allowed to say about that.

## Required behaviour

```
claim state     INCONCLUSIVE        (never REPRODUCED)
evidence class  FINITE_VERIFICATION
headline        "... The claim remains open."
limitation      FINITE VERIFICATION PASS != PROOF
```

Enforced in three places, any of which fails the build:

1. `agent/schemas.py` — `EvidenceClass` has no `PROOF` member.
2. `policy/claim_states.py` — `FINITE_VERIFICATION` evidence cannot support
   claim state `REPRODUCED`. A finite search can *refute* a universal claim by
   counterexample; it can never confirm one.
3. `evidence/certificate.py` — `assert_no_theorem_promotion` rejects promotion
   language and requires the limitation string verbatim on any
   finite-verification certificate.

`tests/adversarial/test_no_theorem_promotion.py` attacks all three.

## Why this belongs in a verification agent

An agent that will happily write "Collatz conjecture verified" after a
successful search will also write "claim confirmed" after a replay that only
happened to agree. The discipline is the same discipline; this is just the case
where the overreach is unmistakable.
