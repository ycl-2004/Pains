# UI acceptance — 2026-09-13

Scope: the existing YC research workspace, all five navigation pages, all 28 current dossiers, responsive layout, local validation records and recovery states. The public evidence, scores and pipeline data are unchanged.

## Fixes

- Mobile navigation meets the 64px header without a gap, displays all five entries and keeps page actions available.
- Below 1280px, opportunities open in a separate detail view. Wider screens use a bounded, independently scrollable list. The full target audience wraps above the summary metrics instead of being clipped into narrow cells.
- Page heading hierarchy and muted text contrast are consistent across themes. Long content wraps without widening the page.
- Search includes opportunity IDs and display titles; active filters are visible and can be cleared. Query state survives refresh and detail return.
- Today continues showing watched signals when a run has no new ones, with an explicit label separating existing signals from new arrivals.
- Notebook changes update other tabs and saved-opportunity views. Backups are available directly from Validation; records remain accessible when their public opportunity has been removed.
- Read failures are distinct from empty records. Failed writes retain an exportable draft. Import preserves existing notes, rejects invalid backups and reports failures. Network failures and malformed data collections show a retry action.

## Verification

The acceptance scenarios use the real exported dataset, plus browser-local fault injection for unavailable data/storage. Fault injection never changes public data or runs a model.

| Area | Acceptance scenario |
| --- | --- |
| Layout | Today, Opportunities, Signals, Validation, Archive and a dossier at 320, 390, 768, 1024, 1280 and 1440 CSS px; no horizontal page overflow; visible page heading |
| Dossiers | All 28 at 320 and 1440px; expand sources and score history; displayed source-link counts match the export |
| Accessibility | axe-core 4.10.3 WCAG A/AA and best-practice scans across six page types, light/dark, 320/1440px; keyboard skip link, filters and selection; reduced motion |
| Navigation | Search, filters, ordering, refresh, desktop selection, narrow-screen detail return and scroll position |
| Notebook | Save text/stage, reload, inspect downloaded JSON, import conflicting/invalid records, retain removed-opportunity notes, cross-tab update |
| Recovery | HTTP failure, delayed load, malformed/empty data, denied storage reads, quota failure, draft backup and unchanged durable record after failed write |
| Release | Python unit tests, Node tests, production build, diff hygiene; commit/push and triggered GitHub checks |

Observed local results: 64 Python tests and 7 Node tests passed; the production build succeeded. All 36 layout combinations and 56 dossier checks passed. The 24-page accessibility matrix reported no violations after transitions settled. Final screenshots were visually reviewed for Today, workbench, mobile, narrow desktop, Signals and Archive.

Run the repository checks:

```sh
.venv/bin/python -m unittest discover -s tests
npm --prefix web test
npm --prefix web run build
git diff --check
```

Use `npm --prefix web run preview -- --host 127.0.0.1` for browser acceptance of the production bundle. Save any existing local notebook/theme values before temporary browser tests and restore them afterward. Do not clear the browser profile.

Browser checks establish behavior in Chromium at the tested viewport sizes; this is not a claim of native-device Safari/Firefox coverage. Source-site availability, paid model execution, buyer evidence accuracy and commercial outcomes are outside this UI audit.
