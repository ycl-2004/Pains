# ADR-001: Buyer evidence before recommendation

Status: accepted · 2026-09-13

## Context

The first two live runs exercised collection and model fallback but not new-cluster creation or web solution checks. Popular developer discussions dominated the 30-item sample. A repeated URL could increment detections; stage failures returned success; a solved competitor check did not update recommendation status.

## Decision

- Keep the Python/JSON/static-site architecture. Preserve seed and historic ledger data.
- Give Make, n8n Community and WooCommerce support feeds two sampling slots per round, other sources one. Rank observable business behavior ahead of popularity within each source. Empty source slots redistribute. This is an explicit sampling preference, not evidence of market size.
- Add buyer, current cost, payment evidence and cited buying-evidence URLs. Money lost is not a purchase commitment. Cap willingness-to-pay at 4 when explicit cited buying evidence is absent from a newly analyzed/updated cluster. Existing seed scores are not silently rewritten.
- Within eligible recommendations, cited buying evidence ranks before overall score. Empty buyer fields remain visible unknowns rather than generated promises.
- Canonicalize URLs, reject invented input references and unknown cluster IDs before applying updates. Re-reading a thread cannot increase detection counts. A resolved thread can supersede its old demand classification. Distinct URLs still do not prove distinct people, organizations or incidents.
- New clusters start in watch. Activation requires at least two distinct demand URLs, behavior evidence, overall >= 5, a B/C solution classification, and a successful solution check. A checks demote and cap overall at 4 and gap at 2. This is a conservative eligibility gate, not a validated probability of profitability.
- Recheck solutions every seven days, at most three per run, reserving a slot for overdue work. Public candidate lists require a recent check. Solution sources must match OpenRouter's returned URL-citation annotations; absent citations are a failure, not permission to invent URLs.
- Revisit up to five supported cited demand threads weekly. GitHub discovery also uses updated time, closed state and the last comments page. No full historical crawl is claimed. Existing unsupported Reddit seed evidence cannot be automatically revisited.
- Retain counterevidence and allow a small second triage pass after replies. Signal updates explicitly reference existing IDs and may promote to a cluster or drop a signal.
- Record success/partial/failed. Incomplete attempts remain immediately retryable and return nonzero. CI commits completed data and the failure report before marking the update job failed; failed updates do not deploy a new site.
- Cache completed model calls under ignored `data/audit/calls/`, keyed by prompt, schema, input, model routes and parameters. These include sanitized input/output and usage for local diagnosis and exact-call replay. Invalid results are quarantined. Cache is not committed, uploaded or restored in Actions: a fresh CI runner cannot resume from it. A remote paid call interrupted before its response arrives remains unrecoverable.
- Estimate request admission from catalog prices and conservative input size, reduce output tokens to fit remaining budget, disable hidden SDK retries and limit request timeout to 180 seconds. This remains a soft budget; hard billing limits belong at the provider. Web search reserves $0.10 but actual provider search costs may vary.
- `npm run dev` exports only; `npm run refresh` explicitly invokes research. Best-effort redaction removes email addresses and recognizable tokens, not every possible personal detail.

## Sources and acceptance evidence

- [Discourse RSS documentation](https://meta.discourse.org/t/finding-discourse-rss-feeds/264134)
- [Discourse API](https://docs.discourse.org/)
- [WordPress support-feed behavior](https://meta.trac.wordpress.org/ticket/2204)
- [GitHub issue API](https://docs.github.com/en/rest/issues/issues)
- [Stack Exchange backoff](https://api.stackexchange.com/docs/throttle)
- [OpenRouter web citation annotations](https://openrouter.ai/docs/guides/features/plugins/web-search)

Read-only probes on 2026-09-13: Make / n8n topic RSS and both WooCommerce-related feeds returned HTTP 200 and 30 entries each. Feed access does not establish completeness or future availability. Regression tests cover the decision rules with simulated responses; live model output quality and paid conversion still require evaluation.
