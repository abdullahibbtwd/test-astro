# UX layout notes

## Checked

- Shared screens and virtualized lists cap readable content at 680dp on wide
  displays.
- Rows, buttons, chips, segmented controls, date paging, headers, and bottom
  sheet titles now shrink or wrap instead of overflowing at 360dp and large
  font settings.
- The welcome footer wraps, and home action labels can use two lines.

## BLOCKED — tablet product decisions

The current centered single-column fallback remains usable. Do not introduce
the following tablet-specific layouts until product/design chooses a pattern:

- **Chart and chart focus:** choose between a larger centered wheel or a
  wheel-plus-reading/table split view, including where chart detail appears.
- **Map, place, area, line, and recommendation results:** choose whether
  reports and filters remain bottom sheets or become a persistent side panel
  beside the map.
- **Calendar month and year/period timeline:** choose whether the month grid
  stays phone-sized and centered or expands, and whether the fixed-width
  timeline scales to the viewport or preserves horizontal scrolling.
- **Ask threads and chat:** choose between the current single route and a
  thread-list/chat split view.
- **Compatibility list and report:** choose whether tablets use separate
  routes or a master-detail layout.
- **Welcome, sign-in, and onboarding:** choose between the full-screen
  ornamental arch and a bounded card/column treatment.

These are product composition decisions, not overflow fixes.
