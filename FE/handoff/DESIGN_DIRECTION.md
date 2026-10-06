# Current design direction

The source of truth for the existing visual language is `FE/src/design-system/`: Night/Parchment semantic colors, Aboreto display text, Poppins UI/body text, the supplied glyphs and thin orbit/star artwork. `FE/src/design/components/` adapts this kit to the app's existing components.

The original kit is supplied separately as `astro-design-kit-original.zip`, including SVG originals, fonts/licences, token files and component reference images. The copied DS_IMPLEMENTATION_SPEC records the original migration brief. Read its phase-gate wording as project history alongside DS_00/01/02 reports and the owner's later instructions.

## Latest owner-approved differences from older mocks

- Birth-first welcome with date/time/place and **Find out who I am**.
- Real core identity generated before account creation, with animated waiting state.
- Reading preview at 40%, sign-in invitation, then 100% feature access and Ahead/Match/Map.
- Bottom-visible language control, small borderless Terms/Privacy links.
- Home city reminder beneath date: **Still in [city]? Change**, with a small dismiss icon; no large bordered notice or prominent timezone string.
- Map parans are ultra-thin.
- Empty chat starters stay upright.

## Refinement priorities

Improve hierarchy, density, spacing, text lengths and reading comfort without removing states or breaking the working flows. The current long test-profile greeting is fixture content; production should use meaningful user-facing names. Give primary actions appropriate prominence and keep secondary settings subtle.

Check long EN/TR copy, two-line buttons, Dynamic Type, reduced motion, long readings, keyboard/sheet overlap and small screens. Preserve large enough hit areas even when controls appear small. Keep selection semantics, loading/retry/cancel actions, offline states and profile context.

Use a screen/state inventory and an annotated design file as the next design deliverable. Do not treat the existing component migration or supplied screenshots as final visual sign-off.
