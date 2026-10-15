# Current status — 3 October 2026

The checked frontend items below describe implemented UI, including sample-server screens. They do not mean every production service exists. The local Android preview now uses real calculations and approved reading pipelines for the core features. Real sign-in requires an account-service choice; Ask, Solar Return and family-specific compatibility remain disabled where no matching live backend is connected.

# Full build checklist

- [x] Chart facts and detail sheets
- [x] Shared wheel model, interaction and parity
- [x] Chart/report exports and share cards
- [x] Generated parts, flags and completion notifications
- [x] Home and Today
- [x] Month, Year and Solar Return
- [x] Compatibility
- [x] Calendar month/day/item/year/periods
- [x] Best Days
- [x] Notification scheduler and preferences
- [x] Astro Map native layers and accessible navigation
- [x] Place/area reports and recommendation flow
- [x] Ask streaming and conversation management
- [x] Account integration/polish
- [x] Targeted Android regression and export checks
- [ ] Production API/OAuth/map/legal integration and iOS/device accessibility/performance acceptance

External requirements to track: final legal content/app identifiers; production API capabilities/credentials; OAuth client configuration; map provider style/worldview; iOS build environment. These do not block independent frontend implementation.

## Local live integration — 2 October

- [x] Real chart engine bridge and input validation
- [x] Durable local profiles/charts and private sessions
- [x] Real calendar, Best Days, notification candidates and daily/monthly facts
- [x] Separate emulator launcher and cache isolation
- [x] Reading-job infrastructure and cumulative US$20 budget guard
- [x] Approved fictional fresh reading: 17 sections, English/Turkish schemas, persisted result and English Android display; budget guard US$0.305641
- [x] Fresh-reading native PDF, Turkish display and saved-report navigation checks
- [x] Live yearly facts, requested-month coverage and event navigation
- [x] Fresh day/month/year forecast prose, bilingual jobs/cache and date alignment
- [x] Forecast Saved Reports and requested date/lens context handling
- [ ] Broader live lens/location acceptance
- [x] Compatibility love/work approved-pipeline wiring and offline regression
- [ ] Fresh paid compatibility acceptance (second fictional profile response pending)
- [x] Real map geometry, all 11 heat layers, places/points, areas and recommendations
- [x] Bilingual map reading jobs, retries and saved history
- [ ] Live Ask backend (frontend exists against scripted contract)
- [ ] Real email/Google/Apple authentication
- [x] Local account JSON export and account deletion, including derived map cache
- [ ] Broader device/accessibility/performance acceptance and production service setup
