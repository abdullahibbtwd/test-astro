# Plans config schema (`config/plans.json`)

Data-driven product matrix for subscriptions and free-tier limits. Owner values are **not** guessed: empty strings / `null` markers must be filled before paid launch.

## Top level

| Field | Type | Meaning |
|-------|------|---------|
| `version` | number | Schema version (currently `1`). |
| `provider` | `"unset"` \| `"revenuecat"` \| `"native"` | Billing integration choice. Keep `"unset"` until the owner picks. |
| `free_launch.entitle_all` | boolean | When `true`, every user is fully entitled (also overridable by `ASTRO_FREE_LAUNCH_ENTITLE_ALL`). |
| `feature_catalog` | object | Canonical feature ids used by gates and entitlements. |
| `plans` | array | Plan definitions (at least `free` and one paid plan). |
| `default_plan_id` | string | Plan used when the user has no active subscription. |
| `notes` | string[] | Human reminders (ignored by loaders). |

## Feature catalog entry

```json
"ask": {
  "id": "ask",
  "description": "Ask Astrology conversations",
  "premium": null
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `id` | string | Stable id (`ask`, `family`, `reports`, `map`, …). |
| `description` | string | Docs only. |
| `premium` | `true` \| `false` \| `null` | `true` = requires a plan that lists this feature. `false` = available on free. `null` = **owner undecided**; enforcement treats the feature as ungated until set. |

## Plan entry

```json
{
  "id": "free",
  "name": "",
  "display_name_en": "",
  "display_name_tr": "",
  "store_product_ids": { "apple": "", "google": "" },
  "features": [],
  "daily_limits": {
    "ask": null,
    "natal_reading": null,
    "map_reading": null,
    "forecast_reading": null,
    "compat_reading": null
  }
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `id` | string | Stable plan id (`free`, `premium`, …). |
| `name` | string | Internal / store-facing label (owner-supplied). |
| `display_name_en` / `display_name_tr` | string | UI labels (owner-supplied). |
| `store_product_ids.apple` / `.google` | string | App Store / Play product ids (owner-supplied). Empty until created in the consoles. |
| `features` | string[] | Feature catalog ids included in this plan. |
| `daily_limits.*` | number \| `null` | Per-UTC-day caps. `null` → fall back to `ASTRO_DAILY_*` env / code defaults. |

### Limit keys

| Config key | Usage counter / env |
|------------|---------------------|
| `ask` | `ASK` / `ASTRO_DAILY_ASK_LIMIT` |
| `natal_reading` | `NATAL_READING` / `ASTRO_DAILY_NATAL_LIMIT` |
| `map_reading` | `MAP_READING` / `ASTRO_DAILY_MAP_LIMIT` |
| `forecast_reading` | `FORECAST_READING` / `ASTRO_DAILY_FORECAST_LIMIT` |
| `compat_reading` | `COMPAT_READING` / `ASTRO_DAILY_COMPAT_LIMIT` |

## Entitlement computation (runtime)

1. If free-launch entitle-all is on → entitlements include `all: true` (and every catalog feature).
2. Else load the user's subscription row; if status is `active` or `grace` and not expired → use that `plan_id`.
3. Else use `default_plan_id` (usually `free`).
4. Entitlements object is `Record<featureId, true>` for features granted by the plan (plus `all` only in free-launch mode).
5. Daily limits resolve from the active plan’s `daily_limits`, with `null` falling back to env defaults.

## What must not live here

- Prices or localized price strings (always from the store SDK at runtime)
- API secrets, shared secrets, or webhook keys
- Real Apple / Google / RevenueCat credentials
