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
