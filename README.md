# Clinical Evidence Review Agent

This Python CLI creates a source-audited abstraction of text clinical records and answers related questions through a bounded, tool-using agent. It is a prototype for one review corpus at a time. Source records remain read-only; every run gets a new output directory.

## Setup

Python 3.11+ and `uv` are recommended:

```bash
uv sync
```

Set a key for a **general-purpose, programmatic model API** in the environment. For Z.AI's regular OpenAI-compatible API, use `ZAI_API_KEY`; for OpenAI, use `OPENAI_API_KEY`. The Anthropic adapter accepts `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`. Keep credentials outside version control and run outputs. A local `.env` file is ignored by Git; load it with `uv run --env-file .env`. Both keys may be set at once: an explicit Z.AI base URL selects `ZAI_API_KEY`, while the default OpenAI endpoint selects `OPENAI_API_KEY`. The [Z.AI Coding Plan endpoint](https://docs.z.ai/devpack/quick-start) is documented for supported coding tools, while the [standard API endpoint](https://docs.z.ai/guides/overview/quick-start) is for programmatic model calls; use the latter for this application with an eligible API key.

For `glm-4.7`, the adapter disables thinking by default to keep extraction and tool responses within the output budget. Set `BB_GLM_THINKING=enabled` to test the reasoning variant. Z.AI documents this [per-turn thinking control](https://docs.z.ai/guides/capabilities/thinking-mode).

## Run

```bash
uv run --env-file .env bb-review \
  --documents documents \
  --questions questions.json \
  --provider openai \
  --model YOUR_MODEL \
  --base-url YOUR_API_BASE_URL \
  --start 2026-01-05 --end 2026-01-30
```

The questions file is a JSON array of strings or `{ "id": "...", "question": "..." }` objects. `--start` and `--end` define an inclusive review period; omit them to include all extracted dates. Results appear in a new `runs/<timestamp>-<random>/` directory:

- `abstraction.json`: source hashes, extracted claims, event reconciliation, unresolved items and audit findings.
- `calculation.json`: event ledger, bounded minutes and sessions, weekly totals and goal decisions.
- `answers.json`: answers, citations and citation audit results.
- `trace.jsonl`: extraction, reconciliation, model and tool calls with token usage.
- `run.json`: model, runtime, source manifest and usage summary.

The original inputs are `documents/` and `questions.json`. The historical GLM run is stored separately in `artifacts/development/` and is never selected by the fresh-run command or the question page. Its answer limitations are listed below.

For a new model, omit `--snapshot`: this forces extraction and reconciliation from the original documents. Model-stage cache reuse is disabled by default. After a successful offline run, later questions with the same model and unchanged documents may reuse its `abstraction.json` through `--snapshot`; the source hashes, model identity, and rejected-claim findings are checked before reuse. `--reuse-cache` is an explicit content-addressed stage option. Do not reuse output from a different model when establishing an independent result.

When `--reuse-cache` is explicitly selected, validated extraction and reconciliation batches are cached by model, prompt and input content under the chosen output root's `_stage_cache/`. Progress messages identify the active batch or question.

## Local question page

First let the new model process the original documents, with a separate output root. `--prepare-only` skips the five development answers so you can ask only the questions you want in the page. The command prints a unique run directory when finished:

```bash
uv run --env-file .env bb-review \
  --documents documents --prepare-only \
  --provider openai --model YOUR_MODEL \
  --base-url YOUR_API_BASE_URL \
  --output runs/new-model \
  --start 2026-01-05 --end 2026-01-30
```

Install the optional Gradio interface and point it to **that new run directory**:

```bash
uv sync --extra web
uv run --env-file .env --extra web bb-review-web \
  --run PATH_PRINTED_BY_BB_REVIEW \
  --provider openai --model YOUR_MODEL \
  --base-url YOUR_API_BASE_URL
```

Open `http://127.0.0.1:7860`, enter a new question, and click **Ask**. The answer appears in the page with its source references. **Download Markdown** provides the same answer as a `.md` file. The page checks the model, source hashes, calculation, and rejected-claim findings before using a saved offline result. It does not rerun document extraction for each question. Each answer and its model trace are saved under ignored `runs/web/`. To generate the original five answers, run `bb-review` separately with `--questions questions.json` and `--snapshot PATH_TO_ABSTRACTION` after the offline run.

The page listens on the local computer only and does not create a public Gradio share link. For another document set, pass its original source directory with `--documents` to both commands and use the run directory created from those documents.

## Method and checks

The source adapter assigns stable document IDs and line numbers and builds a SQLite FTS5 index. A model extracts source-specific event, plan, measurement and observation claims in batches. Source-line labels are normalized to integer anchors when unambiguous. Extraction, time-scope audit, and reconciliation validate complete model outputs; invalid output is sent back to the model with concrete errors for bounded repair, and persistent invalidity stops the stage before an answer can use a partial result. A source-coverage check retries explicitly identified encounters omitted by a large batch. A selective time-scope audit distinguishes group/session time from patient-specific contact time. A reconciliation pass combines claims about the same encounter, retaining explicit corrections and unresolved conflicting intervals. The deterministic calculator unions actual patient-contact intervals, subtracts breaks, aggregates by day and Monday–Sunday week, and compares documented goals. The answer agent can search, open sources, inspect all claims for an event, page through complete inventories and request calculated views. It can investigate a new question even if that concept was absent from the initial abstraction.

The code uses a narrow `ModelPort` (Adapter pattern), `Corpus` source/search port (Repository pattern), and a bounded tool runtime (Agent/Command pattern). The model and storage adapters can be replaced independently. Native `anthropic` and `openai` SDKs provide the wire protocols; Pydantic validates the data contracts. This small tool loop keeps the take-home project runnable without a LangGraph service dependency. LangGraph's `create_agent` is an optional replacement for the same tool protocol if a larger deployment needs middleware or durable execution.

The offline checks cover source addressing, interval union/subtraction, uncertainty bounds and goal comparison. Model-based validation should run the supplied questions first, followed by independent unseen questions. A failed unseen case should be diagnosed at the intake, extraction, identity, reconciliation, calculation or investigation layer instead of patched by question ID.

## Development run and observed limitations

On September 30, 2026, a full run over the 31 supplied fictional text records and five development questions used `glm-4.7` through the standard Z.AI OpenAI-compatible API, with thinking disabled and JSON mode for structured extraction. It made 22 model calls, used 129,253 input and 12,978 output tokens, and took 422.98 seconds. At the [published GLM-4.7 rates](https://docs.z.ai/guides/overview/pricing) of $0.60 per million uncached input tokens and $2.20 per million output tokens, the recorded usage implies approximately **$0.11** before any cached-input discount; this is an estimate, not a provider invoice.

The calculated abstraction contains 20 distinct events, including 12 delivered patient-therapy sessions across 11 dates. It records 585–595 therapy minutes because two signed January 26 notes disagree about the start time. The weekly results are 140, 120, 180 and 145–155 minutes; the last week crosses the documented 150-minute threshold and is indeterminate. All five generated answers contain source-line references that resolve to the supplied files.

**The five answer texts are not fully validated.** In the first answer, the prose says six excluded encounters while its table correctly lists eight. In the second, the prose says 19 total and seven excluded while the event ledger has 20 total and eight excluded. The fourth answer misstates the original January 19 roster arithmetic in one paragraph, despite giving the corrected 60-minute result elsewhere. The fifth makes an overly broad claim about the entire episode from date-specific safety observations. The extraction, reconciliation and deterministic calculation outputs are the stronger current artifacts; do not treat the raw narrative answers as a reviewed clinical conclusion.

The independent questions in `validation/unseen-questions.json` and their prespecified expectations in `validation/unseen-expectations.md` are ready for a replacement-model run. They have **not** been run on the current model. The current implementation also has a design limit beyond model quality: it pre-extracts a fixed set of fact categories, provides lexical line search and fixed calculation views, and sends the full event index to the answer agent. It cannot claim reliable coverage of arbitrary new predicates or performance on tens of thousands of documents. The next architecture investigation is query-time evidence derivation, scoped retrieval and backend aggregation; changing the model alone cannot establish those capabilities.

To evaluate a replacement model independently, run without `--snapshot` and `--reuse-cache`, then compare its new abstraction, source coverage, and answers with the prespecified expectations. The historical GLM output is retained only as an audit record and is not used by this path.

## Limits

The current parser accepts UTF-8 text files. PDF/OCR, multi-tenant access control, distributed indexing and large-corpus benchmarking are extension points, not claimed capabilities. FTS5 is lexical; new terminology may require the agent to scan source inventories or a future hybrid-search adapter. Missing actual-contact time is flagged as `unquantified` and makes totals incomplete. Citation validation checks source IDs and line bounds; semantic support still requires review. `run.json` records token usage rather than a provider invoice; the documented cost is estimated from public rates.

Implementation assistance: OpenAI Codex generated and reviewed the code and architecture. Technical ideas and libraries are credited in [the implementation plan](cn/IMPLEMENTATION_PLAN.md).
