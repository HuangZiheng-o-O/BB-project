# Submission guide

## What this project does

BB Project turns a folder of text records into an inspectable abstraction of a patient's course of care. It preserves each source line, extracts candidate claims, links records that describe the same encounter, retains corrections and conflicts, and calculates delivered treatment from patient-present intervals. A bounded investigation agent then answers new questions with access to the abstraction, original text, and deterministic calculations. Answers cite original document lines and can be reviewed without trusting a search snippet or an unsupported model summary.

The supplied exercise has 31 fictional records in [`data/`](../data/), five specified questions in [`questions.json`](../questions.json), and 22 additional related questions. The system does not hardcode this patient's answers. Start with the [runbook](RUNBOOK.md), inspect the [interactive architecture](https://huangziheng-o-o.github.io/BB-project/architecture.html), or open the [five reviewed development reports](../validated-answers/README.md).

## Where each requested deliverable lives

| Submission requirement | Location |
| --- | --- |
| Runnable code and setup instructions | [`bb/`](../bb/), [`pyproject.toml`](../pyproject.toml), and the [runbook](RUNBOOK.md). |
| Complete clinical abstraction | [`artifacts/reviewed-development/abstraction.json`](../artifacts/reviewed-development/abstraction.json). |
| Deterministic treatment calculations | [`artifacts/reviewed-development/calculation.json`](../artifacts/reviewed-development/calculation.json). |
| Execution logs | [`offline-trace.jsonl`](../artifacts/reviewed-development/offline-trace.jsonl) and [`trace.jsonl`](../artifacts/reviewed-development/trace.jsonl), with corresponding run metadata. |
| Answers to the five specified questions | [`answers.json`](../artifacts/reviewed-development/answers.json) and the readable [`DEV-01`–`DEV-05` reports](../validated-answers/README.md). |
| Source support | Inline `SOURCE_ID:Lx` citations plus exact original lines in each report; source files are in [`data/`](../data/). |
| Approach, checks, settings, assistance and scope | This guide, the [walkthrough](IMPLEMENTATION_WALKTHROUGH.md), [runbook](RUNBOOK.md), and [implementation plan](IMPLEMENTATION_PLAN.md). |

The curated reports include the question, final reviewed answer, evidence excerpts, and online model-call count. The evidence excerpts are copied locally from cited source lines; copying them does not use a model call or model output tokens. The older [`artifacts/development/`](../artifacts/development/) bundle records a separate GLM experiment. Use `artifacts/reviewed-development/` when inspecting the later five-question `gpt-6-sol` evaluation.

## Approach and checks

1. **Index:** [`bb/source.py`](../bb/source.py) assigns stable source IDs, hashes source bytes, addresses every line, and builds a local SQLite full-text index.
2. **Abstract:** [`bb/extract.py`](../bb/extract.py) extracts candidate events, plan goals, measures and observations. [`bb/time_audit.py`](../bb/time_audit.py) checks patient-specific time scope. Validation rejects unverifiable source anchors and returns bounded repair feedback to the model.
3. **Reconcile:** [`bb/reconcile.py`](../bb/reconcile.py) links mentions to encounters, distinguishes actual care from schedules, drafts and copies, and retains conflicting evidence instead of erasing it.
4. **Calculate:** [`bb/compute.py`](../bb/compute.py) unions actual contact intervals, excludes nontherapy time, derives bounded minutes, aggregates weeks, and compares the documented plan goal.
5. **Investigate:** [`bb/agent.py`](../bb/agent.py) chooses among five evidence tools to answer each question. It validates citation addresses and may request a corrected answer when citation audit fails.

The nine current unit tests cover evidence addressing, interval arithmetic and uncertainty, goal comparison, bounded repair, snapshot rejection, agent tool use, and Markdown report generation. Evaluation also used the five development questions and 22 prewritten independent questions; their [reviewed reports](../validated-answers/README.md) expose the underlying sources. Answer keys for the independent questions were prepared outside the searchable repository before the corresponding runs. This is an evaluation of a bounded prototype, not a claim of universal clinical correctness.

## Reproducibility and observed measurements

The reviewed development-answer run used provider `openai`, model `gpt-6-sol`, a validated snapshot from the same model, 31 source files, and the January 5–30, 2026 review window. The CLI defaults were a 13,500-character extraction batch, 12 tool calls per question, and six model turns per question. No temperature override is set in this code. The five-question online run took **101.77 seconds**, made **17 online model calls**, and recorded **136,419 input** and **6,288 output tokens**. These figures come from [`run.json`](../artifacts/reviewed-development/run.json); they do not include the earlier offline model processing.

The matching offline abstraction came from a separate `gpt-6-sol` run whose complete runtime was **214.49 seconds**. That run also answered one question, so its runtime and aggregate token totals are **not** an offline-only measurement. Its run metadata and the filtered offline trace are bundled as [`offline-source-run.json`](../artifacts/reviewed-development/offline-source-run.json) and [`offline-trace.jsonl`](../artifacts/reviewed-development/offline-trace.jsonl). The saved abstraction's SHA-256 is `d2216a18e0363d566f7c24f8bcf504f1a75d7596047ae7bd6d2a3708c7553552` in both runs. The application recorded `cost_usd: null` because a provider billing rate was not supplied. Token usage is available for estimating cost under the reader's applicable account rate; no unsupported price is asserted here.

The snapshot records **12 therapy sessions on 11 distinct days**: five individual, five group and two family sessions. Delivered patient therapy is **585–595 minutes** across the period. The bounds preserve a documented conflict about one encounter; the final week's minute goal remains undetermined from the current evidence. See [`DEV-01`](../validated-answers/DEV-01.md), [`DEV-02`](../validated-answers/DEV-02.md), and [`DEV-03`](../validated-answers/DEV-03.md) for calculations and source lines.

## Observed input boundary and next investigation

The current source adapter ingests UTF-8 `.txt` files. It has not been exercised on scanned PDFs, tables in office documents, or mixed-format enterprise corpora. The next investigation is a parser adapter that emits the same stable source IDs, page or line anchors, and source hashes for PDF and DOCX inputs; a small mixed-format fixture should then be checked for extraction completeness and citation fidelity before changing the review logic. This preserves the current evidence contract while expanding input formats.

## Design and coding assistance

I directed AI-assisted research and led the architecture, discussing detailed design decisions with AI. AI implemented the project, and I worked with AI to review and test it. The [implementation plan](IMPLEMENTATION_PLAN.md) credits the libraries and technical ideas used. The runtime code uses the official `openai` and `anthropic` SDKs, Pydantic contracts, and Python's SQLite interface. No third-party agent source code was copied.
