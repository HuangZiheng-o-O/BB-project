# Implementation Plan and Research Decisions

## Scope

Deliver a working CLI for the supplied text documents, five development questions and related unseen questions. Preserve source-level audit, duplicate control, field-specific corrections, uncertainty ranges, deterministic arithmetic and an agent that can investigate original records.

## End-to-end design

1. **Source adapter:** load UTF-8 `.txt` files read-only, preserve source IDs, SHA-256 hashes and stable line addresses; index lines in SQLite FTS5. Search returns candidates, while paged source inventory permits complete coverage.
2. **Candidate extraction:** batch records into model-sized inputs and produce source-linked event mentions, plan goals, instrument instances and observations. Normalize unambiguous line labels, validate source IDs and line ranges, and feed validation errors back to the model for bounded repair before saving a reusable offline snapshot.
3. **Identity and reconciliation:** group mentions by patient plus encounter/appointment IDs; bridge a uniquely linked appointment ID to an encounter ID. Ask the model for one event decision per group, retaining support, opposition, corrections and multiple plausible interval sets. Return validation feedback for model repair before accepting a batch.
4. **Deterministic calculations:** union patient-contact intervals, subtract nontherapy periods, keep conflicting durations as bounds, count one encounter once and one therapy day per date, aggregate Monday–Sunday weeks, and compare documented targets. Do not infer delivery from schedules, charges or unsigned notes.
5. **Bounded answer agent:** seed it with a compact abstraction index and enable `search`, `open_source`, `related`, `scan` and `calculate`. Model-selected tools can investigate a new predicate directly in source records. Record calls and validate cited source-line addresses.
6. **Reproducibility:** write each run to a unique directory; store abstraction, calculation, answers, source hashes, trace, model name and token usage. Reuse abstraction for new questions after source-hash, model, and validation checks.

## Design patterns and choices

| Pattern | Implementation | Reason |
| --- | --- | --- |
| Ports and adapters | `ModelPort`, `Corpus`, SDK adapters | Switch the model endpoint or search backend without changing review logic. |
| Immutable source ledger | Hashes, source IDs, line anchors | Keep corrections and retransmissions as separate claims. |
| Materialized review view | `ReviewSnapshot` plus deterministic calculation | Reuse abstraction across questions; reduce model calls. |
| Bounded agent | Model-directed tool loop and call budget | Support related unseen questions without a scripted question router. |
| Conservative uncertainty | Interval alternatives and unresolved findings | Avoid false precision from contradictory signed records. |

This implementation uses the official [`openai` SDK](https://github.com/openai/openai-python), [`anthropic` SDK](https://github.com/anthropics/anthropic-sdk-python), [Pydantic](https://docs.pydantic.dev/latest/) and Python's [SQLite interface](https://docs.python.org/3/library/sqlite3.html). The bounded loop follows the native SDK tool-call protocol, with conceptual influence from [LangChain `create_agent`](https://reference.langchain.com/python/langchain/agents/factory/create_agent); no third-party agent source code was copied. The source/evidence separation follows the [Anthropic agent tool-design guidance](https://www.anthropic.com/engineering/writing-tools-for-agents) and [OpenAI's practical agent guide](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf). The exact local code is original.

## Acceptance sequence

1. Verify syntax and the CLI, source hashes and line anchors, interval arithmetic, weekly aggregation and uncertain goal status with generic offline cases.
2. Run the five supplied questions on an eligible programmatic model API. Inspect the abstraction and answer traces for missing or duplicated events, source support, arithmetic and unresolved conflict.
3. Create independent questions before inspecting outputs, including symptom, administrative and conflict queries. Analyze results by intake, extraction, identity, reconciliation, calculation and investigation layer.
4. Record model/version, settings, runtime, token usage, approximate cost when rates are known, and evaluation findings.

The [Z.AI Coding Plan documentation](https://docs.z.ai/devpack/quick-start) identifies its Anthropic endpoint as a supported-coding-tool route. The [standard API guide](https://docs.z.ai/guides/overview/quick-start) describes the general OpenAI-compatible endpoint used for an authorized application run. Credentials must never appear in source files, configuration examples, traces or commits.
