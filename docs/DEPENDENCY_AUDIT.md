# Dependency audit (security hardening)

## npm (backend)

| Severity | Package | Action |
| --- | --- | --- |
| high | `zod` &lt;4.6.6 (DoS on oversized constrained collections) | **Deferred** — upgrade is zod@4 (breaking). Mitigated by `bodyLimit: 65536` and Ask/label caps. |
| moderate | `@sentry/node` → glob/minimatch | **Deferred** — `npm audit fix --force` jumps outside stated range; schedule Sentry bump separately. |
| high→fixed | `fastify` header validation | **Upgraded** to `5.12.8`. |

Safe `npm audit fix` applied; remaining force upgrades not taken.

## npm (frontend)

After safe `npm audit fix`:

| Severity | Package | Action |
| --- | --- | --- |
| high | `zod` | **Deferred** (zod 4 breaking; same as backend) |
| high | `expo-router` | **Deferred** — tied to Expo SDK; needs coordinated upgrade |
| high | `d3-color`, `decode-uri-component`, `query-string` | **Deferred** — transitive via map/router; force may break Expo |
| high | `mapshaper` | **Deferred** — map tooling; evaluate separately |

Reduced from 10 → 6 high via non-breaking lockfile refresh.

## pip (`requirements-handoff.txt`)

| Package | Finding | Action |
| --- | --- | --- |
| `pillow==12.3.0` | 39 advisories; fix `13.0.0` | **Upgraded** to `pillow==13.0.0` |

No other high/critical packages reported by `pip-audit` on this file.
