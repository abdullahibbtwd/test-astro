# PA 03: composer, validator and templates

*The composer phrases evidence; it adds nothing. The validator is deterministic and refuses to ship on any violation
(the project's validator discipline: ACG_04 AV1–AV8, CAL_03 CV1–CV5, ACG_09 RV4 apply, extended here for chat).
Reuse the existing forbidden-word lists, detox and validator framework (Phase 0 item 9); import the lists, don't copy
them.*

## 1. When the composer runs

| Plan / evidence state | Result |
|---|---|
| `smalltalk`, `clarify`, `out_of_scope` | template (§7), no composer call: `smalltalk` hello / thanks / ai_identity → `smalltalk_hello` / `smalltalk_thanks` / `ai_identity`; `clarify` rephrase / person / place → `clarify_rephrase` / `clarify_person` / `clarify_place_missing`; `out_of_scope` → the template named in PA_02 §5 |
| any pack `needs_input` | clarify template with its options (`clarify_place`, `clarify_place_not_found`, `clarify_person`), no composer call |
| every pack `out_of_range` / `absent` / `not_ready` | the matching template (`out_of_range_future`, `no_data`, `not_ready`), no composer call |
| otherwise | composer → validator (§5) → repair / drop / fallback (§6) |

Packs that are `absent`, `out_of_range` or `not_ready` next to usable ones are passed to the composer as status lines
only; their gaps are covered by deterministic notes (§6.3), never by model text.

## 2. Composer inputs

1. **System rules** (§4), stable across users so the provider can cache them.
2. **Subject:** label, relation, `is_self`, `lang`, register (TR **siz**, PA_00 O2).
3. **Plan:** intent, `reframe`, lens, `depth`, answer type and its length range (§3).
4. **Evidence (model view of PA_01 §3):** facts as `id: label`; records as `id: render` + polarity + a `sensitive` flag;
   items as `id: label, dates, band/grade label`; prose as `id: text`; card and link candidates as `id: one-line
   description`; status lines for packs that aren't ok.
5. **History window** (PA_02 §6) and the question.

The validator works on the **internal** evidence, which keeps each record's factor and `about` (needed by PV4); the
model never sees those.

## 3. Answer types and lengths

| Answer type | TR words (`depth: normal`) | `depth: more` |
|---|---|---|
| fact | 20–60 | 40–90 |
| interpretive | 90–180 | 150–260 |
| timing | 80–170 | 140–240 |
| place | 80–160 | 140–240 |
| compatibility | 100–200 | 160–260 |
| mixed | 120–220 | 180–280 |

EN answers are checked against the same ranges ±20%, as TR (ACG_04 AV6 convention). Appended notes (§6.3) don't count.

## 4. Composer prompt rules (`pa_compose.py`)

1. **Voice (PA_00 P4).** A warm, clear, professional astrologer. No name, no persona, no mystical or fatalistic tone
   ("it is written", "destiny"). TR uses **siz**. When the subject is the user, speak to them in the second person.
   When the subject is another saved person, speak about them in the third person by their label.
2. **Evidence only.** Every astrological statement is supported by evidence ids in that segment's `trace`. Never state
   a position, aspect, sign, life area, date, band or grade that isn't in the evidence. Never compute anything.
3. **Shape.** Answer the question directly in the first segment. Then give one or two supporting points. Optionally end
   with one reflective invitation ("this may be a good time to notice…"), never an instruction. At most 3 paragraphs,
   plain text, no lists, no Markdown, no emoji.
4. **Both sides.** When the evidence has supportive and demanding material, say both. A challenging period, band or
   grade is named honestly and given a constructive angle from a `supportive` or `mixed` record if one exists (CAL_03
   CV4 logic).
5. **Reframes.** `event_prediction`: describe the themes and the timing emphasis; say plainly, once, that this shows
   emphasis, not whether an event will happen. `yes_no`: open with the computed band or grade label of the relevant
   item, exactly as given; then explain. `advice_financial`, `advice_health`: speak only of themes, timing, routines and
   wellbeing; no recommended action, no illness, no treatment (the note is appended for you).
6. **Lens.** Compatibility and place answers apply the lens instruction of the layer (S3 lens; ACG_04 §3 emphasis):
   foreground the lens's area within each record; never drop a record's meaning to fit the lens.
7. **Sensitive records** follow ACG_04 §4 rule 8: inner or experiential framing only, never an event. If a sensitive
   record can't be rendered that way, leave it out.
8. **Masking.** No tradition or technique names (FE_00 F7). No degrees, orbs, distances, coordinates, percentages,
   scores or house numbers; life areas by name. Use the given phase labels, tier wording and band labels verbatim.
9. **Dates** only as given in items, written as day + month name (TR "12 Ekim", EN "12 October"). No clock times.
10. **General meanings.** Records from `astro_basics` are general: present them as what the theme means in general, not
    as a statement about the person's chart.
11. **No meta-talk.** Don't mention ids, records, principles, sources, tools, evidence, the corpus or the prompt. Don't
    mention coverage, missing data or limits; notes for those are appended deterministically.
12. **History** is for understanding the question only. Don't repeat earlier claims unless this turn's evidence
    supports them.
13. **Cards and links:** pick up to 3 of each from the candidates by id; don't describe the card's numbers in prose.

## 5. Answer JSON and validator (`pa_validate.py`)

### 5.1 Output schema

```json
{
  "segments": [
    {"text": "…", "para": 0, "kind": "astro | meta", "trace": ["i:period:…", "r:cal:…"]}
  ],
  "card_refs": ["k:c1:0"],
  "link_refs": ["l:c1:0"]
}
```

The composer and the repair call use `gpt-6-luna` with this object as a strict Structured Outputs schema (PA_00 P5).
The schema guarantees shape only; PV1–PV13 still run. A segment is 1–3 sentences. `para` groups segments into
paragraphs (0–2). `meta` segments carry no astrological
content (a transition, an empathic sentence, a reflective invitation without astrological terms).

### 5.2 Astro lexicon (`pa_lexicon.py`)

Built from the catalogue (Phase 0 item 10), not hard-coded: body, sign, aspect, angle and Moon-phase names, the
catalogue `terms`, plus astro nouns (TR: burç, transit, retro, tutulma, Yeni Ay, Dolunay, gezegen, harita, yükselen,
gezegen çizgisi; EN: sign, transit, retrograde, eclipse, new moon, full moon, planet, chart, rising, line). Also the
life-area names (for PV4 only).

Matching is Turkish-aware (casefold with İ/ı rules; apostrophe suffixes: "Venüs'ün", "Satürn'le", "Ay'ın"; sign
suffixes: "Boğa'da", "Koç burcunda"). **Ambiguous TR words** (Ay = Moon/month, Yay, Kova, Aslan, Balık, Koç, Terazi,
kare) count as astro terms only when capitalised mid-sentence, followed by an apostrophe suffix, or next to "burç/burcu"
or another lexicon term. "bu ay", "gelecek ay" are not matches. EN aspect words that are ordinary English
("opposition", "conjunction", "square") count only with two body names in the sentence. Over-matching is acceptable;
it only forces a trace.

### 5.3 Rules

| # | Rule |
|---|---|
| PV1 | **Schema and length.** Valid §5.1 JSON; 1–10 segments; `para` ∈ 0–2; total words within §3 ±20%. |
| PV2 | **Trace validity.** Every trace id exists in this turn's evidence. `card_refs` / `link_refs` exist among the candidates; ≤ 3 each. |
| PV3 | **Astro sentences are traced.** A segment containing a lexicon term (§5.2) has `kind: astro` and ≥ 1 trace id. |
| PV4 | **Claims match the evidence.** In each sentence: (a) a body followed within 6 tokens by a sign → the pair is a natal placement fact, another person's big-three fact, a day Moon-sign item, a lunation/eclipse/ingress item, or the factor of a record traced in that segment; (b) a body within 6 tokens of a life-area name → a natal placement fact, a lunation item's natal life area, a relocated house shift, or a traced record's factor; (c) two bodies with an aspect word between them (≤ 8 tokens) → a natal aspect fact, a transit item (transiting body, aspect, natal point), or a traced record's factor. Anything else → `claim_unsupported`. |
| PV5 | **Bands and grades.** A band, grade or tone label in a segment must belong to an item traced in that segment. With `reframe: yes_no`, the first astro segment contains the band or grade label of a traced item. |
| PV6 | **Numbers.** Digits are allowed only inside date expressions (day + month name, optional year, or a day range within one month), and each such date must be an evidence date or lie within an evidence item's date range. Reject degrees (`°`, `derece`, `degree`), orbs, `%`, clock times, distances (`km`, `mil`, `kilometre`) and house-number patterns (ACG_04 AV1). |
| PV7 | **Forbidden language.** The AV2 (directives), AV8 (event prediction for sensitive themes), RV4 (certainty) lists, plus chat additions: fatalism (TR `kaderiniz`, `kaderinizde`, `yıldızlar böyle istiyor`; EN `destined`, `your fate`, `the stars say`); predicted life events (TR `evleneceksiniz`, `boşanacaksınız`, `hamile kalacaksınız`, `zengin olacaksınız`, `işten çıkarılacaksınız`, `ayrılacaksınız`, `mutlaka olacak`; EN `you will marry`, `you will divorce`, `you will get pregnant`, `you will be rich`, `you will be fired`, `you will break up`, `will definitely`); advice (TR `yatırım yapın`, `hisse alın`, `hisselerinizi satın`, `ilacı bırakın`, `teşhis`, `dava açın`; EN `invest in`, `buy shares`, `sell your shares`, `stop taking`, `diagnos`, `you should sue`; ordinary shopping words stay allowed because Best Days has a shopping activity); illness (TR `hastalık`, `kanser`, `ameliyat`; EN `illness`, `disease`, `cancer`, `surgery`). Turkish-aware, word-boundary matching. |
| PV8 | **Masking.** The FE_02 AC3 unambiguous mask terms plus: Hellenistic, Ottoman, Arabic, classical astrology, traditional astrology, modern astrology, decan, dignity, sect; TR Helenistik, Osmanlı, Arap, klasik astroloji, geleneksel astroloji, modern astroloji, dekan. Merge with the backend's existing list (Phase 0 item 9); TR equivalents of dignity terms are confirmed there. |
| PV9 | **No internal leakage.** No trace-id patterns (`r:`, `f:`, `i:`, `p:`, `k:`, `l:` prefixes), no corpus id patterns (from Phase 0), and none of: principle, record, corpus, evidence, trace, tool, JSON (TR ilke, kayıt, kanıt, araç). |
| PV10 | **Plain text.** No Markdown (`#`, `*`, `_`, backticks, `- ` or `1.` at line start), no emoji, ≤ 3 paragraphs. |
| PV11 | **Language.** The text is in `lang`: a stop-word ratio check (TR vs EN) per paragraph. |
| PV12 | **Naming.** A place answer names the resolved place (`name_tr` in TR, `name` in EN; with `resolved_by: geocoder`, name + country). A compatibility answer names the other person by label. A non-self subject is named by label at least once. |
| PV13 | **No orphan claims about others.** Facts about another person (`f:other:*`) appear only in compatibility answers. |
| PV14 | **Templates are exempt** from PV1, PV3–PV6 and PV12; they must pass PV7–PV11 (checked once in tests, T-templates). |

## 6. Repair, drop, fallback, assembly

### 6.1 Repair

On any violation: one repair call to the composer with the same inputs plus the violation list (rule, segment index,
offending span). The reply is validated again.

### 6.2 Drop or fallback

If the repaired answer still fails: drop the failing segments **only if** the first segment survives, ≥ 1 astro segment
survives, and the remaining words are ≥ 60% of the type's minimum. Otherwise use the `fallback_unreliable` template with
the deterministic default cards and links (§6.4). The audit records `repair`, `dropped_segments`, `fallback`.

### 6.3 Deterministic notes (appended as the last paragraph)

| Condition | Note template |
|---|---|
| any pack `clamped` (calendar / span / day) | `note_coverage_calendar` |
| a `best_days` pack `clamped` | `note_coverage_best_days` |
| a pack `absent` / `out_of_range` / `not_ready` next to usable ones | `note_partial` |
| `recommend` with `thin_result` | `note_thin_result` |
| `reframe: advice_financial` | `note_financial` |
| `reframe: advice_health` | `note_health` |

At most two notes, in the table's order.

### 6.4 Assembly

Text = segments joined by a space within a paragraph, paragraphs joined by `\n\n`, then the notes. Cards = the
validated `card_refs`, or, if none, the first candidate of each call (forced calls first), up to 3. Links likewise,
de-duplicated by route.

## 7. Templates (`pa_templates.json`)

TR uses **siz** (O2). All TR strings go to native review. `{slots}` are filled deterministically.

```json
{
  "crisis_support": {
    "tr": "Bunu yaşadığınız için gerçekten üzgünüm. Bununla tek başınıza yüzleşmek zorunda değilsiniz: lütfen güvendiğiniz biriyle ya da bir ruh sağlığı uzmanıyla konuşun. Acil bir tehlike varsa hemen 112'yi arayın.",
    "en": "I'm really sorry you're going through this. You don't have to face it alone: please reach out to someone you trust or to a mental health professional. If you're in immediate danger, call 112 now."
  },
  "decline_harm": {
    "tr": "Ölüm, hastalık, kaza ya da zarar hakkında öngörüde bulunmuyorum. İsterseniz bir dönemin sizin için duygusal olarak neyi öne çıkardığına birlikte bakabiliriz.",
    "en": "I don't make predictions about death, illness, accidents or harm. If you like, we can look at what a period brings forward for you emotionally."
  },
  "decline_medical": {
    "tr": "Sağlık ya da tıbbi konularda yardımcı olamıyorum. Sağlığınızla ilgili her konuda lütfen bir doktora veya uzman birine danışın. İsterseniz haritanızın günlük ritimleriniz ve alışkanlıklarınız hakkında söylediklerine bakabiliriz.",
    "en": "I can't help with health or medical questions. For anything about your health, please talk to a doctor or another qualified professional. If you like, we can look at what your chart says about your daily rhythms and habits."
  },
  "decline_legal": {
    "tr": "Hukuki tavsiye veremiyorum. Hukuki konular için lütfen bir avukata danışın. İsterseniz bu dönemin sizin için hangi temaları öne çıkardığına bakabiliriz.",
    "en": "I can't give legal advice. For legal matters, please consult a lawyer. If you like, we can look at the themes this period brings forward for you."
  },
  "decline_financial": {
    "tr": "Finansal ya da yatırım tavsiyesi veremiyorum. Bu tür kararlar için yetkin bir finans danışmanına başvurmanız en doğrusu. İsterseniz haritanızın ve takviminizin para konularında genel olarak neyi öne çıkardığına bakabiliriz.",
    "en": "I can't give financial or investment advice. For decisions like this, a qualified financial adviser is the right person to ask. If you like, we can look at what your chart and calendar bring forward for money matters in general."
  },
  "decline_birth_data": {
    "tr": "Gizlilik ve doğruluk için sohbette doğum bilgisi almıyorum. Kişiyi Haritalarım'a eklerseniz haritasına birlikte bakabiliriz.",
    "en": "For privacy and accuracy, I don't take birth details in the chat. Add the person to My Charts and we can look at their chart together.",
    "links": ["add_person"]
  },
  "decline_third_party": {
    "tr": "Yalnızca Haritalarım'a kayıtlı kişilerin hesaplanmış haritaları üzerinden yorum yapabiliyorum. Başka biri hakkında sormak isterseniz önce onu Haritalarım'a ekleyin.",
    "en": "I can only talk about people saved in My Charts, using their computed charts. To ask about someone else, add them to My Charts first.",
    "links": ["add_person"]
  },
  "decline_non_astrology": {
    "tr": "Haritanız, önünüzdeki dönem, yerler ve ilişkileriniz hakkındaki sorular için buradayım. Bu konularda dilediğinizi sorabilirsiniz.",
    "en": "I'm here for questions about your chart, the time ahead, places and your relationships. Ask me anything along those lines."
  },
  "decline_past": {
    "tr": "Son yedi günü ve önümüzdeki on iki ayı inceleyebiliyorum. Daha eski dönemler henüz kapsamımda değil.",
    "en": "I can look at the last seven days and the next twelve months. Earlier periods aren't covered yet."
  },
  "out_of_range_future": {
    "tr": "Takviminiz önümüzdeki on iki ayı, En İyi Günler ise önümüzdeki doksan günü kapsıyor. Bu aralıktaki bir tarih için sorabilirsiniz.",
    "en": "Your calendar covers the next twelve months, and Best Days the next ninety days. Ask me about a date within that range."
  },
  "no_data": {
    "tr": "Bu soru için haritanızda dayanabileceğim bir veri bulamadım. Soruyu biraz farklı sorabilir misiniz?",
    "en": "I couldn't find anything in your chart data to base an answer on for that. Could you ask it a little differently?"
  },
  "not_ready": {
    "tr": "Bu soru için verileriniz hâlâ hazırlanıyor. Lütfen bir dakika sonra yeniden sorun.",
    "en": "Your data for this is still being prepared. Please ask again in a minute."
  },
  "smalltalk_hello": {
    "tr": "Merhaba! Haritanız, önünüzdeki günler, yerler ya da ilişkileriniz hakkında dilediğinizi sorabilirsiniz.",
    "en": "Hello! Ask me anything about your chart, the days ahead, places or your relationships."
  },
  "smalltalk_thanks": {
    "tr": "Rica ederim. Başka bir şeye bakmak istediğinizde buradayım.",
    "en": "You're welcome. I'm here whenever you want to look at something else."
  },
  "ai_identity": {
    "tr": "Ben bir yapay zekâ asistanıyım. Hesaplanmış harita verilerinizi açıklarım; gezegen konumlarını kendim hesaplamam ya da uydurmam.",
    "en": "I'm an AI assistant. I explain your computed chart data; I don't calculate planetary positions myself or make them up."
  },
  "clarify_rephrase": {
    "tr": "Sorunuzu tam anlayamadım. Biraz farklı ifade edebilir misiniz?",
    "en": "I'm not sure I understood. Could you put your question another way?"
  },
  "clarify_place": {
    "tr": "Hangi yeri kastediyorsunuz: {options}?",
    "en": "Which place do you mean: {options}?"
  },
  "clarify_place_missing": {
    "tr": "Hangi yere bakmamı istersiniz? Şehrin adını yazabilirsiniz.",
    "en": "Which place would you like me to look at? Just write the city name."
  },
  "clarify_place_not_found": {
    "tr": "Bu yeri bulamadım. Şehrin adını, gerekirse ülkesiyle birlikte yeniden yazabilir misiniz?",
    "en": "I couldn't find that place. Could you write the city name again, with its country if needed?"
  },
  "clarify_person": {
    "tr": "Kimin haritasıyla karşılaştırmak istersiniz? Haritalarım'dan birini seçebilir ya da yeni bir kişi ekleyebilirsiniz.",
    "en": "Whose chart would you like to compare with? Choose someone from My Charts or add a new person.",
    "links": ["add_person"]
  },
  "fallback_unreliable": {
    "tr": "Bu soruya güvenle dayanabileceğim bir yanıt oluşturamadım. Aşağıdaki ayrıntılar doğrudan hesaplanmış verilerinizden geliyor.",
    "en": "I couldn't put together an answer I can stand behind for that question. The details below come straight from your computed data.",
    "tr_no_cards": "Bu soruya güvenle dayanabileceğim bir yanıt oluşturamadım. Soruyu biraz farklı sorabilir misiniz?",
    "en_no_cards": "I couldn't put together an answer I can stand behind for that question. Could you ask it a little differently?"
  },
  "note_coverage_calendar": {
    "tr": "Takviminiz önümüzdeki on iki ayı kapsadığı için yanıt bu aralıkla sınırlı.",
    "en": "Your calendar covers the next twelve months, so this answer stays within that range."
  },
  "note_coverage_best_days": {
    "tr": "En İyi Günler önümüzdeki doksan günü kapsadığı için yanıt bu aralıkla sınırlı.",
    "en": "Best Days covers the next ninety days, so this answer stays within that range."
  },
  "note_partial": {
    "tr": "Bu sorunun bir kısmı için verileriniz henüz hazır değil ya da kapsam dışında.",
    "en": "For part of this question your data isn't ready yet or is outside the covered range."
  },
  "note_thin_result": {
    "tr": "Bu hedef için öne çıkan yer sayısı az; liste bilerek kısa tutuldu.",
    "en": "Few places stand out for this goal, so the list is deliberately short."
  },
  "note_financial": {
    "tr": "Bu sembolik bir yansımadır, finansal tavsiye değildir.",
    "en": "This is a symbolic reflection, not financial advice."
  },
  "note_health": {
    "tr": "Bu sembolik bir yansımadır, tıbbi tavsiye değildir.",
    "en": "This is a symbolic reflection, not medical advice."
  }
}
```

`{options}` = up to 4 options as "İzmir, Türkiye" joined with ", " and "ya da" / "or" before the last. Template links
come from the PA_01 §6 table (`add_person` → `/profiles/new`).

## 8. Acceptance (`test_pa_validate.py`, `test_pa_compose.py`)

| # | Check |
|---|---|
| V1 | One positive and one negative unit test for each of PV1–PV13. |
| V2 | Turkish morphology for PV3/PV4: "Venüs'ünüz", "Ay'ın", "Koç burcunda" match; "bu ay", "gelecek ay", "bir kare" (no bodies) don't. |
| V3 | PV4 fixtures on the reference chart: "Venüs'ünüz Koç burcunda" when Venus is in another sign → `claim_unsupported`; the true placement passes; an invented aspect between two natal bodies → `claim_unsupported`; a transit item's aspect passes. |
| V4 | PV6: a date not in the evidence → violation; a date inside a period's range passes; "15°", "3. ev", "10:30" → violation. |
| V5 | Repair path: a scripted bad answer then a scripted good one → shipped, `repair: true`. Drop path: the second answer fails in its last segment only → that segment dropped. Fallback path: the second answer fails in its first segment → `fallback_unreliable` with default cards. |
| V6 | §6.3 notes appear exactly under their conditions, at most two. |
| V7 | Every template exists in TR and EN, slots fill correctly, and each passes PV7–PV11 (T-templates). |
| V8 | Scripted composer answers for the 6 FE_09 starter prompts on the reference chart pass the validator unchanged. |
| V9 | The composer prompt contains no internal fields (factor keys, `about`, `_tradition`, scores) and no digits except dates (inspect the built prompt with `--dry-run`). |
