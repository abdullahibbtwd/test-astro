# SYNASTRY_RUN_CHANGES.md — changes to `synastry_run.py` for the reading-type fork

**Design:** ground once (type-agnostic), fork in S3. So the orchestrator's job is only to (a) get the `reading_type` from the user, (b) feed the tagged corpus, and (c) pass the type through to S3 and stamp it into meta. Grounding still runs exactly once. Six changes; the first four are required, the last two optional.

Depends on: `SYNASTRY_READING_PROFILES.md` (S3 accepts `reading_type`) and `GROUND_RELATIONSHIP_CONTEXTS.md` (tagged corpus).

---

## 1. Select `reading_type` — prompt + flag (required)

Add a CLI flag and an interactive prompt, default `general`.

In `main()` arg parsing (alongside `--model` etc.):

```python
ap.add_argument("--reading-type", choices=["general", "personal", "professional"],
                default=None, help="relationship reading focus; prompt if omitted")
```

After the API-key/corpus guards, before collecting people, resolve it:

```python
reading_type = args.reading_type
if reading_type is None:
    print("\nWhich relationship reading?\n"
          "  [1] General        — the connection as a whole\n"
          "  [2] Personal focus — romantic / life partnership\n"
          "  [3] Professional   — business / working partnership")
    reading_type = {"1": "general", "2": "personal", "3": "professional",
                    "": "general"}.get(run._prompt("Choose [1/2/3] (default 1): ").strip(),
                                       "general")
print(f"reading_type = {reading_type}")
```

Ask it **before** the label step (§2 needs it). Reuse `run._prompt` for consistency with the rest of the input flow.

---

## 2. Type-aware default labels (required)

The current defaults are `sen` / `partnerin` — "partnerin" (your partner) is wrong for a professional reading and misleading for general. Make person B's default depend on `reading_type`:

```python
_B_DEFAULT = {"personal": "partnerin", "professional": "iş ortağın", "general": "diğer kişi"}
label_a = _optional_label("Person A", "sen")
label_b = _optional_label("Person B", _B_DEFAULT[reading_type])
```

(Person A stays `sen`. Adjust the Turkish to your house style; the point is the default must not import a romantic frame into a professional or general reading.)

---

## 3. Point the corpus at the tagged file (required)

`REL_CORPUS_PATH` currently hardcodes `combined_relationship_principles.clean.json`. The fork needs the corpus that carries `synastry.contexts`. Either repoint the constant to `combined_relationship_principles_tagged.json`, or replace that file's contents with the tagged version. Grounding's new E6 invariant (see `GROUND_RELATIONSHIP_CONTEXTS.md` §2) will hard-fail here if an untagged corpus is fed — which is the intended safety net; surface that error clearly rather than catching it.

---

## 4. Pass `reading_type` into S3 (required — the actual wiring)

The grounded `payload` is produced once, unchanged. The fork happens inside `read_relationship`, which filters the payload by context, picks the section structure, applies the lens, and writes the type into its routing report. So thread the type through the S3 call:

```python
output, statements_doc, report, errors = read_relationship(
    payload, reading_type=reading_type,
    label_a=label_a, label_b=label_b,
    houses_valid=houses_valid, precision_detail=precision_detail,
    **read_kwargs)
```

No other S3-call change. `read_relationship` owns eligibility filtering, sections, emphasis, and lens per `SYNASTRY_READING_PROFILES.md`; the orchestrator just supplies the type.

---

## 5. Stamp `reading_type` into `run_meta` + surface the context split (required)

**5a.** Add `reading_type` to `write_meta`. Give the function a parameter and put it in the meta dict (near `"reading": "relationship"`):

```python
def write_meta(status, models=None, tz_a=None, tz_b=None,
               counts=None, houses_valid=None, reading_type=None):
    meta = {
        "run_id": run_id,
        "reading": "relationship",
        "reading_type": reading_type,
        ...
```

Pass `reading_type=reading_type` at **every** `write_meta(...)` call site (the error-path calls too, so a failed run still records which type was attempted).

**5b.** Grounding's payload now carries `counts["contexts"]` (per `GROUND_RELATIONSHIP_CONTEXTS.md` §3). Surface the split for the chosen type in the `[L2/L3]` print, so a thin professional slice is visible before the (expensive) S3 call:

```python
ctx = counts.get("contexts", {}).get("synastry", {})
print(f"[L2/L3] grounded: ... (context split synastry {ctx})  reading_type={reading_type}")
```

---

## 6. Optional

- **Thin-slice guard.** For `professional`, the admitted per-person slice is small (~29 records). Optionally, if the eligible count for the chosen type falls under a floor, print a one-line warning ("professional slice is thin for this pair; the working-partnership opener will be brief") — informational, not a halt.
- **Encode type in the readable filename.** One run is one type and `run_meta` records it, so this isn't required. But if you ever generate more than one type per couple, disambiguate the readable stem: `write_readable(..., stem=suffixed(f"relationship_reading.{reading_type}", suffix))`. The JSON artifacts can stay stable names or take the same treatment.
- **Multi-type from one grounding.** Because grounding is type-agnostic and already done, offering "generate another focus?" at the end is just another `read_relationship(payload, reading_type=...)` call on the same `payload` — no re-run of L1–L3. Worth it only if users commonly want two views of the same pair; otherwise skip.

---

## What does NOT change

- **Grounding is called once, unchanged.** `ground_relationship(corpus, chart_a, chart_b)` stays type-agnostic; do not filter or re-ground per type in the orchestrator.
- **L1 / wheels / geocoding / run-id / suffix rule** — untouched; all reused from `run.py` as now.
- **The contract-violation gate** (don't write the reading on S3 errors) — unchanged; it already writes the routing report either way, which now carries `reading_type`.

---

## Change map (quick reference)

| # | location in `synastry_run.py` | change |
|---|---|---|
| 1 | `main()` argparse + pre-collect | `--reading-type` flag + interactive prompt |
| 2 | label step | type-aware default for `label_b` |
| 3 | `REL_CORPUS_PATH` constant | tagged corpus |
| 4 | `read_relationship(...)` call | add `reading_type=reading_type` |
| 5 | `write_meta` def + all call sites; `[L2/L3]` print | stamp `reading_type`; surface context split |
| 6 | optional | thin-slice warning / filename / multi-type |
