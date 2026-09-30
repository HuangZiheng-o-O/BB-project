# Reviewed development run artifacts

This directory joins the reusable abstraction created by one `gpt-6-sol` run with the five-question evaluation that reused it. Their `abstraction.json` files have the same SHA-256 hash: `d2216a18e0363d566f7c24f8bcf504f1a75d7596047ae7bd6d2a3708c7553552`.

| File | Origin and meaning |
| --- | --- |
| `abstraction.json` | The complete validated source-linked extraction, reconciliation, findings and source hashes used by the five-question run. |
| `calculation.json` | Deterministic event, week, goal and measure views for January 5–30, 2026. |
| `answers.json` | The five development questions, generated answers, citation audits and online call counts. |
| `run.json` | Five-question online run metadata: `gpt-6-sol`, 31 documents, 17 online calls, 101.77 seconds and token usage. `snapshot_reused` is true. |
| `trace.jsonl` | The five-question online model and tool turns. |
| `offline-trace.jsonl` | The 19 `extract`, `time_scope`, `time_scope_decisions` and `reconcile` entries filtered from the earlier run that produced the identical abstraction. |
| `offline-source-run.json` | Metadata for that earlier run; its 214.49-second duration includes one online answer and must not be read as offline-only time. |

The [five readable reports](../../validated-answers/README.md) include exact original evidence lines and repository-relative links to the [source documents](../../data/). See the [submission guide](../../doc/SUBMISSION.md) for checks, limitations and cost interpretation, and the [runbook](../../doc/RUNBOOK.md) for reproduction commands. The older `artifacts/development/` directory is a separate GLM experiment and is not the provenance of these five reviewed reports.
