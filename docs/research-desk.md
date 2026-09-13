# YC research desk — design and behavior

## Visual decisions

The app uses a portable subset of `YC_Brand_Style/tokens.css`, not its demo JavaScript. The neutral work surface is paired with wine `#8E2C3A` for judgment/actions and denim `#346294` for evidence, with YC paper tones retained in the source tokens. Wine is not an error color. Dark mode uses lighter semantic counterparts. The app is sans-first; mono is reserved for IDs and dates so the interface reads like a working tool, not a generated editorial page.

The fixed desktop sidebar groups Today, Opportunities, Signals, Validation and Archive; mobile uses a compact horizontal navigation. Today leads with a light summary strip, a “needs your judgment” table, signals and source health. The workbench is a dense ~380px list plus detail at desktop widths, and list-to-detail navigation below 768px. Full titles and source paraphrases remain available. Fourteen baseline `short_title` additions are display abbreviations only; no score, evidence, dates or historical judgments were changed. Future analysis can supply a maximum-32-character short title.

Motion is a 200ms opacity/translation entrance when changing dossiers. Native details replace the broken conditional-mount accordion. Reduced-motion, keyboard focus, skip-to-content and small-screen overflow are checked.

## State and privacy

Search, industry, evidence lens, classification, sorting and selected dossier are in hash query parameters. Share the full URL to preserve these filters. Detail return links preserve the workbench query. Session scroll positions are best-effort; unavailable storage does not block navigation.

Validation stage and notes are local to this browser/origin under `pain-radar-research-v1`. No account, sync or upload occurs. Export backs up all local records; import validates record shapes and preserves existing local records on ID conflict. Clear-browser-data operations can delete notes. Do not store sensitive contact information. Local notes are personal observations and do not change shared rankings. Industry familiarity and written delivery constraints are deliberately separate from evidence quality; there is no opaque personal-fit score.

## Evidence and pipeline contracts

- `qualification` is computed once in Python for both run recommendations and web exports. It includes eligibility, reasons and expiry. Static clients reject expired or missing qualification rather than reimplementing the policy. Expiry is the UTC midnight after the seventh full calendar day following the check.
- A successful fetched thread only gets a 7-day success timestamp after it reaches completed judgment. Failed fetch attempts are persisted, with 1/2/4/7-day backoff, so broken links do not occupy every run's five slots. Successfully fetched but unconsumed items retry after one day. Old string timestamps remain supported.
- `refresh_scope` distinguishes original-and-replies from replies-only. HN, GitHub and available Discourse originals refresh; WordPress is replies-only. Bounded replies are not full-thread coverage. Prompts must not represent stale paraphrases as freshly checked originals.
- New source counters report model-triaged demand, buying and counter signals entering analysis. Legacy reports show unknown values, not zero. They are not precision, unique buyers or conversion rates. Per-source ad/duplicate yield, reading time and dollar allocation remain unmeasured; shared model-call costs cannot honestly be split by source without more instrumentation.
- Historical `budget_or_payment` labels may include losses under the previous rubric. The UI calls these amount statements, not confirmed purchase evidence. New prompts exclude losses alone from this kind. URL traceability is not semantic verification.

## Evaluation and release checks

See [commercial calibration](../evals/README.md): 20 provisional synthetic cases and an offline scorer. Model accuracy, clustering independence and conversion require human-reviewed real samples; unit test success does not establish those outcomes.

Run `.venv/bin/python -m unittest discover -s tests`, `npm --prefix web test`, `npm --prefix web run build` and `git diff --check`. Browser QA covers actual baseline content at 320/390/768/1024/1440 widths, both themes, filter refresh, mobile return navigation and notebook persistence/backup.

Implementation references: [React state identity](https://react.dev/learn/preserving-and-resetting-state), [History.replaceState](https://developer.mozilla.org/en-US/docs/Web/API/History/replaceState), [Algolia HN API](https://hn.algolia.com/api).
