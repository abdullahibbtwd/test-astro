# Secret scan report

Generated during security hardening. **No secret values are recorded here.**

## Controls added

- `.gitignore`: ignore `.env` and `.env.*`, allow `*.example`
- `.dockerignore`: exclude env files from image context
- `.gitleaks.toml` + `.github/workflows/secret-scan.yml`
- `.githooks/pre-commit` (enable with `git config core.hooksPath .githooks`)

## History scan

See CI `secret-scan` workflow on full clone (`fetch-depth: 0`). Local result from this hardening pass is recorded below after the scan command runs.

## EXPO_PUBLIC_*

See `docs/EXPO_PUBLIC_ENV.md` — none are backend secrets.

## Local full-history result (this pass)

- Tool: gitleaks detect (redacted)
- Commits scanned: 212
- **Findings: 0**

## Layer 9 follow-up

- CI `secret-scan` uses `fetch-depth: 0` (full history / all reachable commits).
- Workflow includes a planted-secret smoke step that **must fail** when a known fake AWS key is present.
