# Clinical Evidence Review Agent

This Python CLI creates a source-audited abstraction of text clinical records and answers related questions through a bounded, tool-using agent. It is a prototype for one review corpus at a time. Source records remain read-only; every run gets a new output directory.

## Setup

Python 3.11+ and `uv` are recommended:

```bash
uv sync
```

Set a key for a **general-purpose, programmatic model API** in the environment. For Z.AI's regular OpenAI-compatible API, use `ZAI_API_KEY`; for another OpenAI-compatible service, use `OPENAI_API_KEY`. The Anthropic adapter accepts `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`. Keep credentials outside the repository and run outputs. The [Z.AI Coding Plan endpoint](https://docs.z.ai/devpack/quick-start) is documented for supported coding tools, while the [standard API endpoint](https://docs.z.ai/guides/overview/quick-start) is for programmatic model calls; use the latter for this application with an eligible API key.

## Run

```bash
uv run bb-review \
  --documents /path/to/documents \
  --questions /path/to/questions.json \
  --provider openai \
  --model glm-4.7 \
  --base-url https://api.z.ai/api/paas/v4/ \
  --start 2026-01-05 --end 2026-01-30
```

The questions file is a JSON array of strings or `{ "id": "...", "question": "..." }` objects. `--start` and `--end` define an inclusive review period; omit them to include all extracted dates. Results appear in a new `runs/<timestamp>-<random>/` directory:

- `abstraction.json`: source hashes, extracted claims, event reconciliation, unresolved items and audit findings.
- `calculation.json`: event ledger, bounded minutes and sessions, weekly totals and goal decisions.
- `answers.json`: answers, citations and citation audit results.
- `trace.jsonl`: extraction, reconciliation, model and tool calls with token usage.
- `run.json`: model, runtime, source manifest and usage summary.

For follow-up questions over **unchanged** documents, use `--snapshot /path/to/prior/abstraction.json` with a new questions file. Every source hash must match; this avoids repeating extraction and reconciliation calls. Adding documents requires a fresh abstraction.

## Method and checks

The source adapter assigns stable document IDs and line numbers and builds a SQLite FTS5 index. A model extracts source-specific event, plan, measurement and observation claims in batches. A second model pass reconciles claims about the same encounter, retaining explicit corrections and unresolved conflicting intervals. The deterministic calculator unions actual patient-contact intervals, subtracts breaks, aggregates by day and Monday–Sunday week, and compares documented goals. The answer agent can search, open sources, inspect all claims for an event, page through complete inventories and request calculated views. It can investigate a new question even if that concept was absent from the initial abstraction.

The code uses a narrow `ModelPort` (Adapter pattern), `Corpus` source/search port (Repository pattern), and a bounded tool runtime (Agent/Command pattern). The model and storage adapters can be replaced independently. Native `anthropic` and `openai` SDKs provide the wire protocols; Pydantic validates the data contracts. This small tool loop keeps the take-home project runnable without a LangGraph service dependency. LangGraph's `create_agent` is an optional replacement for the same tool protocol if a larger deployment needs middleware or durable execution.

The offline checks cover source addressing, interval union/subtraction, uncertainty bounds and goal comparison. Model-based validation should run the supplied questions first, followed by independent unseen questions. A failed unseen case should be diagnosed at the intake, extraction, identity, reconciliation, calculation or investigation layer instead of patched by question ID.

## Limits

The current parser accepts UTF-8 text files. PDF/OCR, multi-tenant access control, distributed indexing and large-corpus benchmarking are extension points, not claimed capabilities. FTS5 is lexical; new terminology may require the agent to scan source inventories or a future hybrid-search adapter. Missing actual-contact time is flagged as `unquantified` and makes totals incomplete. Citation validation checks source IDs and line bounds; semantic support still requires review. Cost is left null unless a provider rate is supplied, while token usage and elapsed time are logged.

Implementation assistance: OpenAI Codex generated and reviewed the code and architecture. Technical ideas and libraries are credited in [the implementation plan](cn/IMPLEMENTATION_PLAN.md).
