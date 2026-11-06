# UX accessibility checklist

Scope: item 7 audit of key chart, map, home, account, and shared controls.

## Fixed

- [x] Added explicit button names to the chart's Sun, Moon, and Rising controls, including the current sign.
- [x] Exposed the chart wheel as an image when a screen reader is off and hid the gesture-only wheel when it is on. The existing ordered planet buttons remain the screen-reader alternative.
- [x] Exposed the map canvas as an image with a hint directing screen-reader users to Search and List, which provide operable alternatives to map gestures.
- [x] Added the missing accessible name to the shared DatePager Today action and made long-press-only rows expose a button role.
- [x] Added optional hint support to the shared IconButton.
- [x] Confirmed shared IconButton and Chip targets are at least 44dp. Key back, segmented, calendar, map, chart, and home controls also meet the 44dp minimum.
- [x] Restored the AppText font-size cap in segmented controls and applied a 1.5 cap to key raw TextInput instances.
- [x] Replaced the compatibility score's raw Text with AppText.
- [x] Reviewed shared semantic colors in both themes. Text colors meet the documented token contrast ratios; control boundaries use `borderControl`, not decorative `hairline`.
- [x] Kept primary actions after supporting content in source order; modal sheets use `accessibilityViewIsModal`.

## Manual TalkBack / device verification needed

- [ ] Traverse Home, Chart, Map, Compatibility, and authentication screens in source order and confirm focus never lands behind an open sheet.
- [ ] Confirm the chart wheel is skipped by TalkBack and that planet buttons, Focus mode, Reset zoom, tabs, and detail-sheet controls are reachable in a logical order.
- [ ] Confirm Map Search and List provide complete keyboard/TalkBack access without requiring tap, pan, pinch, or long-press gestures.
- [ ] Confirm MapLibre attribution remains announced or otherwise available alongside the map description.
- [ ] Exercise Android back from every sheet, search result overlay, chart detail, and map layer/legend/list surface.
- [ ] Test at Android font sizes 100%, 150%, and maximum. Check segmented labels, map search, OTP entry, chips, and translated Turkish strings for clipping.
- [ ] Verify 44-48dp targets on a physical small-screen device, especially compact chips, calendar cells, header back, chart overlays, and map controls.
- [ ] Run light/dark visual checks with a contrast analyzer for map line colors and band colors. These encode data and are not shared ink/surface tokens, so no palette changes were made in this pass.
- [ ] Verify external keyboard focus indication and order. React Native mobile focus-ring behavior requires device-level testing.
- [ ] Confirm disabled and selected states are announced for chips, tabs, profile choices, and date navigation.
