# Commercial judgment calibration

20 author-written synthetic cases exercise seller/buyer confusion, losses versus budgets, resolved versus closed, prompt injection, false negatives and non-software problems. Labels are provisional: have a human reviewer correct them before using them as a benchmark. This is not a claim about real model precision.

Run a chosen model separately with the production triage prompt and these case texts; do not include `expected`. Save one `{id, kind, codable}` prediction per case, then run `python -m radar.evaluate predictions.json`.

The scorer rejects missing/duplicate IDs and reports classification and codability separately by simple/boundary stratum. Tests validate the scorer, not the model. No paid calls are made by this command.

Before changing model routes or claiming commercial accuracy, add at least 50 human-reviewed real cases, including rejected source items. Blind-review source-to-claim fidelity, same-incident duplication and incorrect cross-workflow merges separately. The last two synthetic cases flag these review needs but their label score does not measure clustering. Track false buying claims as a hard failure; do not hide them in an average score. Record model, prompt revision, cost, sample size and disagreement notes with each evaluation.
