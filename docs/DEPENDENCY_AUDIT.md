# Dependency audit (security hardening)

## npm (backend)

| Severity | Package | Recommendation |
| --- | --- | --- |
| high | `zod` &lt;4.6.6 (DoS on oversized constrained collections) | **Defer / accept risk** until zod@4 migration. Mitigated by `bodyLimit: 65536` + Ask/label caps. Schedule zod 4 as a dedicated PR. |
| moderate | `@sentry/node` → glob/minimatch | **Defer** — force bump is outside stated range; upgrade Sentry on next telemetry pass. |
| high→fixed | `fastify` header validation | **Fixed** — upgraded to `5.12.8`. |

## npm (frontend)

| Severity | Package | Recommendation |
| --- | --- | --- |
| high | `zod` | **Defer / accept** (same as backend; shared validators) |
| high | `expo-router` | **Defer** — requires Expo SDK coordinated upgrade; fix with next SDK bump |
| high | `d3-color`, `decode-uri-component`, `query-string` | **Defer** — transitive via map/router; do not force without Expo QA |
| high | `mapshaper` | **Defer / accept** for now — offline map tooling path; revisit when touching map pipeline |

Safe `npm audit fix` applied on lockfiles; remaining highs need coordinated upgrades.

## pip (`requirements-handoff.txt`)

| Package | Finding | Recommendation |
| --- | --- | --- |
| `pillow==12.3.0` → many advisories | Fix `13.0.0` | **Fixed** — bumped to `pillow==13.0.0`. Re-run engine + Chart_wheel tests after upgrade. |
