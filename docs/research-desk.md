# YC research desk — design and behavior

## Visual decisions

The app uses a portable subset of `YC_Brand_Style/tokens.css`, not its demo JavaScript. The neutral work surface is paired with wine `#8E2C3A` for judgment/actions and denim `#346294` for evidence, with YC paper tones retained in the source tokens. Wine is not an error color. Dark mode uses lighter semantic counterparts. The app is sans-first; mono is reserved for IDs and dates so the interface reads like a working tool, not a generated editorial page.

The fixed desktop sidebar groups Today, Opportunities, Signals, Validation and Archive; mobile shows all five navigation entries in one row directly below the header. Today leads with a light summary strip, a “needs your judgment” table, signals and source health. When no new signals arrive, Today shows existing watched signals with an explicit no-new-signals label. The dossier summary wraps the complete target audience above three compact evidence/status fields. The workbench is a scrollable ~340px list plus detail from 1280px, and list-to-detail navigation on narrower screens. Full titles and source paraphrases remain available. Fourteen baseline `short_title` additions are display abbreviations only; no score, evidence, dates or historical judgments were changed. Future analysis can supply a maximum-32-character short title.

Motion is a 200ms opacity/translation entrance when changing dossiers. Native details replace the broken conditional-mount accordion. Reduced-motion, keyboard focus, skip-to-content and small-screen overflow are checked.

## State and privacy

Search, industry, evidence lens, classification, sorting and selected dossier are in hash query parameters. Share the full URL to preserve these filters. Detail return links preserve the workbench query. Session scroll positions are best-effort; unavailable storage does not block navigation.

Validation stage and notes are local to this browser/origin under `pain-radar-research-v1`. No account, server sync or upload occurs. Export backs up all local records; import validates record shapes and preserves existing local records on ID conflict. Clear-browser-data operations can delete notes. Do not store sensitive contact information. Local notes are personal observations and do not change shared rankings. Notebook changes update other open tabs and the saved-opportunity lens. Validation provides backup controls directly; notes for opportunities no longer in the public ledger remain visible and exportable. Read errors are distinguished from empty records, and failed writes retain an exportable draft. A failed data load or invalid top-level export shows a retry action. Industry familiarity and written delivery constraints are deliberately separate from evidence quality; there is no opaque personal-fit score.

## Evidence and pipeline contracts

- `qualification` is computed once in Python for both run recommendations and web exports. It includes eligibility, reasons and expiry. Static clients reject expired or missing qualification rather than reimplementing the policy. Expiry is the UTC midnight after the seventh full calendar day following the check.
- A successful fetched thread only gets a 7-day success timestamp after it reaches completed judgment. Failed fetch attempts are persisted, with 1/2/4/7-day backoff, so broken links do not occupy every run's five slots. Successfully fetched but unconsumed items retry after one day. Old string timestamps remain supported.
- `refresh_scope` distinguishes original-and-replies from replies-only. HN, GitHub and available Discourse originals refresh; WordPress is replies-only. Bounded replies are not full-thread coverage. Prompts must not represent stale paraphrases as freshly checked originals.
- New source counters report model-triaged demand, buying and counter signals entering analysis. Legacy reports show unknown values, not zero. They are not precision, unique buyers or conversion rates. Per-source ad/duplicate yield, reading time and dollar allocation remain unmeasured; shared model-call costs cannot honestly be split by source without more instrumentation.
- Historical `budget_or_payment` labels may include losses under the previous rubric. The UI calls these amount statements, not confirmed purchase evidence. New prompts exclude losses alone from this kind. URL traceability is not semantic verification.

## Retention

The scheduled run performs bounded cleanup after saving each report. Raw fetches are kept for 14 days, run reports for 90 days, ledger snapshots for 180 days, and local model-call audit files for 14 days. Archived clusters remain available for 365 days after their last activity; stale signals are removed after 90 days; each cluster keeps the latest 52 score events. `seen.json` remains capped at 50,000 keys. These windows can be overridden with the corresponding `RADAR_*_RETENTION_DAYS` variables. A manual `radar export` only rebuilds the site and never deletes data.

## Evaluation and release checks

See [commercial calibration](../evals/README.md): 20 provisional synthetic cases and an offline scorer. Model accuracy, clustering independence and conversion require human-reviewed real samples; unit test success does not establish those outcomes.

Run `.venv/bin/python -m unittest discover -s tests`, `npm --prefix web test`, `npm --prefix web run build` and `git diff --check`. Browser QA covers actual baseline content at 320/390/768/1024/1440 widths, both themes, filter refresh, mobile return navigation and notebook persistence/backup. See the [UI acceptance record](ui-acceptance.md) for the current audit and recovery scenarios.

Implementation references: [React state identity](https://react.dev/learn/preserving-and-resetting-state), [History.replaceState](https://developer.mozilla.org/en-US/docs/Web/API/History/replaceState), [React effect lifecycle](https://react.dev/reference/react/useEffect), [browser storage events](https://developer.mozilla.org/en-US/docs/Web/API/Window/storage_event), [sticky positioning](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/position), [Algolia HN API](https://hn.algolia.com/api).
