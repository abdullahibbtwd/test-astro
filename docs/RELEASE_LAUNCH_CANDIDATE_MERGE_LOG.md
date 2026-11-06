# release/launch-candidate merge log

Base: `main` @ `65c907b`. Branch: `release/launch-candidate`.
Do not push to main. Do not deploy.

## Pre-start
- Fixed `backend/tests/map-reading-bridge.test.ts`: forces `ASTRO_ALLOW_PAID=0` for unpaid gate; adds paid-path test expecting `/context/i`.
- Tests: 2/2 pass.

## Layer 1 — chore/tsx-node-import, ci/backend-tests
- `ci/backend-tests`: already ancestor of main/RC — no merge needed.
- `chore/tsx-node-import`: cherry-picked `a73c5c5` only (full branch was based on payments/setup-docs and would have pulled payments early).
- Conflicts: none.
- Layer 1 test results: backend map+rate 11/11 pass (fail 0); frontend schema 3/3 pass (fail 0).

## Layer 2 — interpretation / solar / family / benchmark
- `feature/interpretation-rules-config`: already in main/RC — no merge. Conflicts: none.
- `feature/solar-return-api`: already in main/RC — no merge. Conflicts: none.
- `feature/family-compatibility-math`: already in main/RC — no merge. Conflicts: none.
- `feature/benchmark-harness`: already in main/RC — no merge. Conflicts: none.

## Layer 3 — feature/http-rate-limit
- `feature/http-rate-limit`: already in main/RC — no merge. Conflicts: none.

## Layer 4 — launch/* safety
- `launch/compat-score-null`: already in main/RC — no merge. Conflicts: none.
- `launch/map-tiles-setup`: already in main/RC — no merge. Conflicts: none.
- `launch/ai-budget-safety`: already in main/RC — no merge. Conflicts: none.
- `launch/ask-enablement-safety`: already in main/RC — no merge. Conflicts: none.
- Layer 2–4 verification tests: backend 31/31 pass (fail 0); native 2 passed, 2 total.
- Conflicts: none (branches already on main).

## Layer 5 — payments/* (stack order)
- `payments/product-matrix`: merged cleanly. Conflicts: none.
  - post-merge tests: 17/17 pass (fail 0)
- `payments/backend-entitlements`: merged cleanly. Conflicts: none.
  - post-merge tests: 5/5 pass (fail 0)
- `payments/enforcement`: merged cleanly. Conflicts: none.
  - post-merge tests: parse failed
- `payments/provider-abstraction`: merged cleanly. Conflicts: none.
  - post-merge tests: 4/4 pass (fail 0)
- `payments/webhook`: merged cleanly. Conflicts: none.
  - post-merge tests: 3/3 pass (fail 0)
- `payments/mobile-screens`: merged cleanly. Conflicts: none.
  - mobile-screens: no payments native tests yet on this tip; skipped.
- `payments/account-deletion`: merged cleanly. Conflicts: none.
  - post-merge tests: 5/5 pass (fail 0)
- `payments/setup-docs`: merged cleanly. Conflicts: none.
  - setup-docs: docs-only tip; conflicts: none.
  - re-ran enforcement tests (prior multi-file argv glitch): ℹ tests 11 ℹ pass 11 ℹ fail 0 
