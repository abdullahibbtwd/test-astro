# Benchmark fixtures

Astrologer-facing benchmark cases for Solar Return (and later Family) math.

**Do not invent expected values.** Add real benchmark JSON only after the
astrologer (or an approved ephemeris reference) supplies them. Until then the
harness tests **skip cleanly**.

## Layout

```
backend/tests/fixtures/
  README.md                 # this file
  benchmark.schema.json     # JSON Schema for one case
  benchmarks/               # one JSON file per case (*.json)
```

## Case schema (summary)

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable slug (`kano_2024`) |
| `kind` | yes | `"solar_return"` (extend later for `"family"`) |
| `birth` | yes | Birth data: `date` (YYYY-MM-DD), `time` (HH:MM), `latitude`, `longitude`, optional `place` / `tz` |
| `target_year` | yes for solar | Return year |
| `expected.return_utc` | yes for solar | Expected return instant (ISO-8601 UTC) |
| `expected.ascendant` | no | Expected Asc sign and/or longitude |
| `expected.key_placements` | no | Named placements to assert (body → sign / longitude) |
| `sample_reading` | no | Approved sample prose (null until astrologer delivers) |
| `mapping` | no | Notes linking placements → reading sections |
| `notes` | no | Free-form provenance |

Full machine schema: [`benchmark.schema.json`](./benchmark.schema.json).

## Adding a case

1. Copy the template below into `benchmarks/<id>.json`.
2. Fill only fields the astrologer / reference source verified.
3. Leave `sample_reading` null until copy exists.
4. Run `npm test` in `backend/` — the harness picks up the file automatically.

### Template

```json
{
  "id": "example_solar_2025",
  "kind": "solar_return",
  "birth": {
    "date": "1990-01-15",
    "time": "08:30",
    "latitude": 41.0082,
    "longitude": 28.9784,
    "place": "Istanbul",
    "tz": "Europe/Istanbul"
  },
  "target_year": 2025,
  "expected": {
    "return_utc": "2025-01-14T12:00:00Z",
    "ascendant": { "sign": "Aries", "longitude": null },
    "key_placements": []
  },
  "sample_reading": null,
  "mapping": {},
  "notes": "Replace with astrologer-approved reference."
}
```
