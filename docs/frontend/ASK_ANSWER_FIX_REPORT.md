# Assistant answer rejection fix — 6 October 2026

The reported contract-timing question reached the connected model and deterministic calculation successfully. The saved audit shows both written drafts rejected by `PV12_naming`: the selected additional profile was labelled `My chart`, and the answer omitted that exact label. The app then displayed its generic fallback with the calculated card.

Live diagnosis also found that Best Days described a supportive window without supplying the matching validation label. Other retries repeated forbidden wording because the repair received rule codes without explanations or offending words.

## Changes

- Share the required profile/person/place labels between composer and validator; explicitly include them in initial and repair instructions.
- Supply the existing forbidden phrases before drafting. On repair, provide the failed rules from PA_03 and precise rejected phrases, unsupported ratings and invalid evidence references.
- Attach the existing supportive label to calculated Best Days windows in English and Turkish.
- Preserve the answer checks, one-repair limit, fallback, account data and shared spending cap. Repair details stay out of public streams and saved audits.

## Verification

- New regressions failed before each corresponding fix.
- Full assistant suite: **86 passed**.
- Original question replayed through the frontend Python bridge: a composed answer passed all checks after one repair.
- Android emulator: resent the original question in its existing conversation. The saved response is `composed`; its repaired draft has no validation violations. Saved before, entered-question and after screenshots.
- Private diagnostic files are in `.tooling/`; emulator screenshots are in `frontend/artifacts/ask-answer-fix/`. These generated outputs are ignored by Git.

The running API starts a fresh Python bridge for each question, so new questions use the change without an Android rebuild. Existing fallback messages remain as conversation history.
