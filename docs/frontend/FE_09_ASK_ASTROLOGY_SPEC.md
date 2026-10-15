# FE 09: Ask Astrology (AI assistant)

*Brief §13. API: FE_02 §7.10 (NEW). The brief's technical rule is binding: **the AI never determines or invents
planetary positions.** The backend computes; the model only explains computed data. On the app side that means:
the app sends the user's words and context ids, never chart numbers, and renders what comes back.*

## 1. Entry points

| From | Context sent |
|---|---|
| Ask button (every tab header) | none (active profile) |
| Home "Ask about your day…" | `{ date: today }` |
| Chart: reading section "…" menu → Ask | `{ section_key }` |
| Today / calendar day → "Ask about this day" | `{ date }` |
| Calendar item → "Ask about this" | `{ item_id }` |
| Best Days day → "Ask about this day" | `{ activity, date }` |
| Place report → "Ask about {place}" | `{ place_id }` |
| Compatibility report → "Ask about this relationship" | `{ compatibility_id, other_profile_id }` |
| Month forecast → Ask | `{ month }` |

Flag `askAstrology` off → every entry point is hidden.

## 2. Screens

### 2.1 Threads (`ask/index`, modal stack)
`GET /ask/threads`: rows with the title (the first question, set by the server), subject profile chip, date.
**New conversation** → `POST /ask/threads { profile_id }` (the active profile) → chat. Swipe → delete.

### 2.2 Chat (`ask/[threadId]`)
- Header: subject profile chip (whose chart is discussed; changing it starts a new thread), info button (the
  disclaimer, §5).
- **Empty thread:** six starter prompts from the brief (chrome, native review), as tappable chips:

| TR | EN |
|---|---|
| Aşk hayatımda nasıl bir dönem başlıyor? | What kind of period is starting in my love life? |
| Bu ay yeni bir iş için uygun mu? | Is this month good for starting a new business? |
| Astrokartografiye göre Londra bana uygun mu? | Is London good for me according to astrocartography? |
| Bu kişiyle uyumum nasıl? | What's my compatibility with this person? |
| Bu ayki en iyi günlerim hangileri? | Which are my best days this month? |
| Haritamda Satürn ne anlama geliyor? | What does Saturn mean in my chart? |

  "…this person" first opens the My Charts picker and attaches `other_profile_id`.
- **Context chip** above the composer shows attached context ("Konu: İzmir", "Konu: 12 Ekim"), removable.
- **Messages:** user messages right-aligned in a `surfaceAlt` bubble; assistant answers left-aligned, full width,
  serif `reading` style (not a bubble). While streaming: a caret and, before the first token, a status line from
  `status` events ("Checking your calendar…", "Looking at your map…"; labels per source kind, chrome).
- **Cards** (§4.3) render inline in the order received; **links** render as chips under the answer and navigate
  inside the app.
- Message actions (long-press / "…"): Copy · Share · thumbs up / down. Thumbs-down offers reasons (Not accurate · Not relevant
  · Too vague · Other) → `POST /ask/messages/{id}/feedback`.
- **Composer:** multiline, 1–1,000 characters, **Send**; while streaming it becomes **Stop** (aborts the request;
  the partial answer stays, marked interrupted).
- **Quota:** when `me.ask_quota` leaves ≤ 5, show "3 questions left today"; at 0 the composer is disabled with the
  reset time (`resets_at`, local).
- Offline: threads readable from cache; composer disabled with a note.

## 3. Behaviour rules (app side)
- Send only `text` and `context` ids. Never attach chart data, degrees or computed values to a request.
- Render assistant text as plain text (C3); no Markdown. Cards and links are the only structure.
- Never rewrite, summarise or post-process the assistant's text.
- Chart facts shown in cards are formatted from structured fields with the catalogue (C8), never parsed out of text.

## 4. Contract

### 4.1 Request
`POST /ask/threads/{thread_id}/messages?lang=` with `Accept: text/event-stream`:

```ts
interface AskRequest { text: string; context?: AskContext }
interface AskContext {
  date?: ISODate; month?: string; place_id?: string; other_profile_id?: string;
  compatibility_id?: string; item_id?: string; activity?: Activity; section_key?: string;
}
```

### 4.2 Stream events

| `event:` | `data:` | Meaning |
|---|---|---|
| `status` | `{ phase: 'understanding' \| 'computing' \| 'writing'; sources: { kind: AskSourceKind; label: string }[] }` | progress; `sources` = which computed resources the backend consulted |
| `delta` | `{ text: string }` | append to the answer |
| `card` | `AskCard` | structured block (§4.3) |
| `link` | `{ label: string; route: string }` | in-app deep link (app routes, FE_01 §3.2) |
| `done` | `{ message_id: string; quota: { used_today: number; limit_per_day: number } }` | end; refresh `me.ask_quota` locally |
| `error` | `Problem` | the answer failed; show inline Retry (re-sends the same text + context) |

`AskSourceKind = 'chart' | 'natal_reading' | 'forecast' | 'calendar' | 'best_days' | 'acg' | 'compatibility'`.
Use `expo/fetch` streaming (FE_01 §1); reconnect is not attempted mid-answer (Retry instead).

### 4.3 Cards

```ts
type AskCard =
  | { type: 'chart_fact'; body: Body; sign: Sign; degree_in_sign: number; house: number; retrograde: boolean }
  | { type: 'best_days'; activity: Activity; days: { date: ISODate; grade: Grade }[] }
  | { type: 'place'; place_id: string; name: string; country_code: string;
      cards: { goal: Goal; band: PlaceBand; band_label: string }[] }
  | { type: 'period'; period: PeriodRef }
  | { type: 'transit'; transit: TransitEpisode }
  | { type: 'compatibility'; compatibility_id: string; labels: [string, string]; compat_type: CompatType }
  | { type: 'forecast'; horizon: 'day' | 'month' | 'year'; date?: ISODate; month?: string; title: string };
```
Each card has a tap target to the matching screen. Unknown `type` → ignored (logged).

### 4.4 Stored messages
```ts
interface Thread { thread_id: string; profile_id: string; title: string;
                   created_at: ISODateTime; updated_at: ISODateTime; messages?: Message[] }
interface Message { message_id: string; role: 'user' | 'assistant'; text: string;
                    cards: AskCard[]; links: { label: string; route: string }[];
                    status: 'complete' | 'interrupted' | 'failed'; feedback?: 'up' | 'down';
                    created_at: ISODateTime }
```

### 4.5 Backend requirements (for Radul's backend agent; context only)
A tool-using model over the API's **own computed resources** (chart, natal reading, forecasts, calendar, Best Days,
ACG place scores and reports, compatibility), never over raw ephemeris; every answer reports its `sources`; TR and
EN; the existing forbidden-word / no-directive / no-event-prediction validator discipline (ACG_04 AV2 / AV8,
CAL_03 CV3) and the tradition mask; no medical, legal or financial advice; the daily quota; no birth data in logs.

## 5. Disclaimer
Shown in the chat info sheet and once as a quiet line at the top of every new thread (chrome):
TR "Yanıtlar senin hesaplanmış haritana dayanır; öz-farkındalık içindir, tavsiye değildir."
EN "Answers are based on your computed chart. They're for self-reflection, not advice."

## 6. States
Streaming, interrupted (Stop), failed (Retry), quota exhausted, offline, flag off (hidden). A thread whose subject
profile was deleted opens read-only with a note.

## 7. Mock
Scripted streams (20–40 ms per chunk) for each starter prompt, each with at least one card and one link, reusing
sentences from the fixture readings (FE_02 §10); plus a failing script, a quota-exhausted script and a slow
"computing" script (8 s of `status` before the first `delta`).

## 8. Acceptance

| # | Check |
|---|---|
| AK1 | Each starter prompt streams an answer with its card(s) and link(s); links open the right screens. |
| AK2 | Requests contain only `text` and `context` (inspect the mock's request log: no numbers from the chart). |
| AK3 | Stop keeps the partial answer marked interrupted; Retry after an `error` event re-sends the same text and context. |
| AK4 | Quota: the counter appears at ≤ 5; at 0 the composer is disabled with the local reset time. |
| AK5 | Entry points attach the right context (verify each row of §1 in the request log). |
| AK6 | Flag `askAstrology` off hides every entry point; `new_off` scenario (404) hides them too. |
| AK7 | VoiceOver / TalkBack announce streamed answers when complete, not token by token. |
