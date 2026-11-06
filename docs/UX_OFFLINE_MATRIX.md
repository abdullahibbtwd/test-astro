# Offline UX matrix

The app restores successful cached queries for up to 30 days. Generated readings
are retained indefinitely by the in-memory query policy, subject to the persisted
cache's 30-day maximum age. Job polling, guest-core data, and `/geo/*` responses
are not persisted. If a screen has no cached data, query wrappers synthesize a
`NetworkError` and the shared error notice uses `errorOffline`.

`offline` means saved information is visible. `offlineDisabled` means the
specific action needs a connection. Existing local navigation, language/theme
selection, copy, and share remain available.

| Main screen / routes                                                      | Works offline                                                                                      | Disabled offline                                                                  | Message key                                         |
| ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------- |
| Home (`/(tabs)`)                                                          | Cached home summary, scores, links, and ready generated text                                       | Refresh and generation/retry                                                      | `errorOffline`; `offlineDisabled` on disabled retry |
| Chart (`/(tabs)/chart`, focus, reading, section)                          | Cached profiles, chart, catalogue, and ready readings                                              | Refresh and new/retry generation                                                  | `offline`; `errorOffline`; `offlineDisabled`        |
| Ahead (`/(tabs)/ahead`, today, month, year)                               | Cached day/month/year forecast views and local date/lens navigation                                | Uncached dates, refresh, and new/retry generation                                 | `errorOffline`; `offlineDisabled`                   |
| Calendar, day, item, periods, year, best days                             | Cached calendar pages, events, and ready generated text                                            | Uncached pages, load more, refresh, and new/retry generation                      | `errorOffline`; `offlineDisabled`                   |
| Match list and reports (`/(tabs)/match`, `/match/[id]`, family)           | Cached list pages and ready compatibility reports                                                  | Load more, delete, refresh, and report generation                                 | `errorOffline`; `offlineDisabled`                   |
| New match (`/match/new`)                                                  | Cached people can be selected and form choices edited                                              | Create report                                                                     | `offlineDisabled`                                   |
| Map (`/(tabs)/map`, full, point, line)                                    | Cached map data and local map interaction; recent map choices                                      | Uncached heat/line data and refresh                                               | `errorOffline`                                      |
| Place and area reports                                                    | Cached place/area facts and ready generated text                                                   | Uncached reports and new/retry generation                                         | `errorOffline`; `offlineDisabled`                   |
| Recommend form/result                                                     | Form editing and a cached result for the identical request                                         | Submit a new recommendation and new/retry generation                              | `offlineDisabled`; `errorOffline`                   |
| Ask thread list (`/ask`)                                                  | Cached threads can be opened; local cached pages remain visible                                    | New conversation, load more, delete, refresh                                      | `offlineDisabled`; `errorOffline`                   |
| Ask chat (`/ask/[threadId]`)                                              | Cached messages, locally persisted draft/messages, copy, and share                                 | Send/retry answer, feedback, and server-side profile switch                       | `offlineDisabled`; `errorOffline`                   |
| Charts/profile editor (`/profile/charts/*`)                               | Cached profiles and local form editing                                                             | Save, delete, and place lookup/confirmation                                       | `offlineDisabled`; `errorOffline`                   |
| Account/settings (`/profile`, settings, privacy, notifications, location) | Cached account data, local language/theme controls, and static/legal content already bundled       | Server mutations, export, location reverse lookup, and place lookup/confirmation  | `offlineDisabled`; `errorOffline`                   |
| Saved reports (`/profile/reports`)                                        | Cached report list and locally available report content                                            | Load more, delete, reset, and refresh                                             | `errorOffline`; `offlineDisabled` on retry          |
| Export (`/chart/export`)                                                  | Cached ready reading can be formatted, copied, or shared locally                                   | Fetch or generate missing reading                                                 | `errorOffline`; `offlineDisabled`                   |
| Subscription/paywall (`/profile/subscription`, `/paywall`)                | Cached entitlement/account fallback may be displayed; store-management URL can be opened by the OS | Product loading, purchase, and restore                                            | `offlineDisabled`; `errorOffline`                   |
| Sign-in (`/(auth)/welcome`, `/link`)                                      | Static welcome and explanatory content                                                             | Provider sign-in, email code/link request, resend, and code verification          | `offlineDisabled`                                   |
| Onboarding (`/(onboarding)/[step]`, auth core/unlocked)                   | Local date/time/name form state and already cached/recent place display                            | Consent/profile saves, place search/confirmation, reverse geocode, and generation | `offlineDisabled`; `errorOffline`                   |
| Solar return (`/solar-return/[year]`)                                     | Cached return for the selected year/place                                                          | Uncached year and retry                                                           | `errorOffline`; `offlineDisabled`                   |
| About                                                                     | Bundled app information                                                                            | Nothing                                                                           | None                                                |

## Shared behavior

- Query screens keep rendering cached successful data while offline; the
  synthesized offline error is only added when no usable data exists.
- Pagination uses the same no-cache synthesis as single-resource and generated
  queries.
- The shared error notice disables retry/request-generation controls offline.
- Place search fields and confirmation are disabled offline, while recent saved
  places remain visible.
- Ask send, new thread/report/recommendation generation, purchases, restores,
  and sign-in requests are guarded before starting network work.

## BLOCKED

None. The existing cache policy determines availability; this change does not
alter feature flags or introduce a new product entitlement decision.
