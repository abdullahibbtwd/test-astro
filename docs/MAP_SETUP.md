# Map tiles setup (MapLibre)

The mobile map uses **MapLibre** (`@maplibre/maplibre-react-native`). Base tiles
come from a **MapLibre style JSON URL** configured on the API — never hard-coded
in the app binary, and never commit API keys.

## Env vars (API / Coolify)

| Variable | Required | Notes |
| --- | --- | --- |
| `ASTRO_MAP_STYLE_LIGHT` | optional | Absolute **https** style JSON URL for light theme. Empty → outline preview. |
| `ASTRO_MAP_STYLE_DARK` | optional | Same for dark theme. |

Flow: Coolify env → `applyMapStyleEnv()` → `GET /meta/config` → `map_style_url.{light,dark}` → MapLibre.

**Do not** put secrets in these URLs if avoidable: the values are sent to every
install via `/meta/config`. Prefer tokenless public styles, or a server-side
proxy that does not embed keys in the client URL.

Demo placeholder (no key): `https://demotiles.maplibre.org/style.json`

### Coolify

1. Open the API service → Environment.
2. Set `ASTRO_MAP_STYLE_LIGHT` and `ASTRO_MAP_STYLE_DARK` to your https style URLs.
3. Redeploy the API only (no mobile rebuild required for URL changes).
4. Confirm `GET /v1/meta/config` shows non-empty `map_style_url`.

### EAS / mobile builds

No map style secrets belong in `eas.json` or `EXPO_PUBLIC_*`. The app reads styles
from the API. Point the app at the Coolify API (`EXPO_PUBLIC_API_URL` / existing
API base). Rebuild the app only when MapLibre native code changes — not when
rotating style URLs.

## Fallback (outline preview)

When the style URL is empty, the device is offline, or the style fetch fails,
the map draws **Natural Earth country outlines** from `GET /v1/geo/countries.geojson`
and shows a gentle caption (`previewMap` / `previewMapOffline` / `previewMapFailed`).
ACG lines and heat overlays still draw on top of the preview.

## Attribution

- Provider styles: MapLibre `attribution` ornament stays **on** (required by most
  tile vendors and by MapLibre demotiles / OSM-derived data).
- Preview mode: caption credits Natural Earth (public-domain outlines).

## Turkey borders & TR/EN labels

| Topic | Finding |
| --- | --- |
| Borders | Preview outlines use Natural Earth countries (Turkey as `TR`). Provider styles depend on the vector tile schema behind the style URL (usually include Turkey). |
| Place names | Client rewrites symbol `text-field` to `coalesce(name:{lang}, name)` for the app language (`en` / `tr`). There is **no** separate TR vs EN style URL — only light/dark. |
| Switching language | Changing app language refetches/rebuilds the style with `name:tr` or `name:en`. If the tile set lacks `name:tr`, labels fall back to `name`. |
| Style by language | Not supported via env today. Add a second pair of env vars only if a future provider needs fully separate TR/EN styles. |

## `/geo/regions` (404)

Live API and OpenAPI ship **only** `/geo/countries.geojson`. Region reports and
`/geo/regions/{iso2}.geojson` are **not** implemented for launch. The recommend
UI no longer navigates to `kind=region`; Area screen shows an unavailable message
if opened with `kind=region`.

## Device test checklist

1. With style URLs empty: outline preview + caption; pan/zoom works; lines/heat align.
2. Set Coolify style URLs (demotiles or production): tiles load; attribution visible.
3. Toggle light/dark theme: matching style URL used.
4. Toggle EN/TR: labels prefer `name:en` / `name:tr` when present.
5. Airplane mode: falls back to outline preview with offline caption; overlays still usable from cache when present.
6. Low-end device: open Map tab, pan across Turkey, toggle heat — no freeze >2s; memory acceptable.
7. Open a country area from recommend; confirm region rows are non-navigable / unavailable copy.
