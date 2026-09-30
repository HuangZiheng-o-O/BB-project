"""Command-line entry point for a reproducible, source-audited review run."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bb.agent import EvidenceTools, answer_question
from bb.compute import calculate_review
from bb.extract import extract_corpus
from bb.model_provider import make_model
from bb.models import ReviewSnapshot, validate_snapshot_reuse
from bb.reconcile import reconcile_events
from bb.report import model_call_count, render_answer_markdown
from bb.source import Corpus
from bb.time_audit import audit_time_scope


def _write_json(path: Path, value: Any) -> None:
    """Create one auditable artifact without overwriting an existing file."""
    # Exclusive creation prevents an accidental rerun from replacing evidence.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


def _read_questions(path: Path) -> list[dict[str, str]]:
    """Accept string or identified-object questions with stable fallback IDs."""
    # Data is the user-supplied JSON question collection.
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Questions file must contain a JSON array")
    # Questions normalizes both supported input forms to ID/text pairs.
    questions = []
    for index, item in enumerate(data):
        if isinstance(item, str):
            questions.append({"id": f"Q-{index + 1:03d}", "question": item})
        elif isinstance(item, dict) and isinstance(item.get("question"), str):
            questions.append({"id": str(item.get("id", f"Q-{index + 1:03d}")), "question": item["question"]})
        else:
            raise ValueError(f"Invalid question at index {index}")
    return questions


def _run_directory(parent: Path) -> Path:
    """Allocate a unique directory for the artifacts of one review run."""
    parent.mkdir(parents=True, exist_ok=True)
    # Name combines UTC time and random bytes to avoid run collisions.
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    # Target is the isolated directory for this run's outputs.
    target = parent / name
    target.mkdir(exist_ok=False)
    return target


def run(args: argparse.Namespace) -> Path:
    """Prepare evidence once, calculate deterministically, then answer questions."""
    # Started measures total wall-clock runtime across all stages.
    started = time.monotonic()
    # Output owns this run's index, snapshot, reports, and trace.
    output = _run_directory(args.output)

    def progress(message: str) -> None:
        """Write timestamped progress to stderr, leaving stdout scriptable."""
        # Timestamp marks each stage transition in UTC.
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        print(f"[{timestamp}] {message}", file=sys.stderr, flush=True)

    progress("Indexing source documents")
    # Corpus reads originals and builds a local line-level search index.
    corpus = Corpus(args.documents, output / "index.sqlite3")
    # Model is one provider adapter shared by offline and online stages.
    model = make_model(args.provider, args.model, args.base_url)
    # Trace accumulates model and validation activity for the complete run.
    trace: list[dict[str, Any]] = []
    if args.snapshot:
        progress("Validating reusable abstraction")
        # Snapshot reuse requires matching model identity and source hashes.
        snapshot = ReviewSnapshot.model_validate_json(args.snapshot.read_text(encoding="utf-8"))
        validate_snapshot_reuse(snapshot, args.model, corpus.manifest())
    else:
        # Model-derived stages are shared by every question in this run.
        # Cache directory is optional and scoped to the output root.
        cache_dir = args.output / "_stage_cache" if args.reuse_cache else None
        # Extraction contains source claims; findings and trace record issues.
        extraction, findings, extraction_trace = extract_corpus(
            corpus, model, max_chars=args.batch_chars,
            cache_dir=cache_dir, progress=progress,
        )
        trace.extend(extraction_trace)
        # Time audit checks whether group clock spans actually describe patient presence.
        time_findings, time_trace = audit_time_scope(
            extraction, corpus, model, cache_dir=cache_dir, progress=progress,
        )
        findings.extend(time_findings)
        trace.extend(time_trace)
        # Reconciliation merges claims about the same clinical encounter.
        reconciliation, more_findings, reconciliation_trace = reconcile_events(
            extraction, corpus, model, cache_dir=cache_dir, progress=progress,
        )
        trace.extend(reconciliation_trace)
        # Snapshot binds all offline decisions to source and model identity.
        snapshot = ReviewSnapshot(
            source_hashes=corpus.manifest(),
            extraction_model=args.model,
            extraction=extraction,
            reconciliation=reconciliation,
            findings=findings + more_findings,
        )
    _write_json(output / "abstraction.json", snapshot.model_dump())
    progress("Calculating event and weekly totals")
    # Calculation uses validated decisions; the model performs no arithmetic here.
    calculation = calculate_review(
        snapshot.reconciliation, snapshot.extraction, args.start, args.end, findings=snapshot.findings,
    )
    _write_json(output / "calculation.json", calculation)
    # Tools expose the snapshot, source lines, and complete calculated views.
    tools = EvidenceTools(corpus, snapshot, calculation)
    # Answers stores structured results; reports stores readable Markdown.
    answers: list[dict[str, Any]] = []
    # Prepare-only runs stop after offline processing and calculation.
    questions = [] if args.prepare_only else _read_questions(args.questions)
    reports = output / "reports"
    if questions:
        reports.mkdir(exist_ok=False)
    # Keep offline preparation calls separate from question-specific calls.
    offline_model_calls = model_call_count(trace)
    online_model_calls = 0
    for number, item in enumerate(questions, 1):
        # Only these question-specific turns count toward the report's online calls.
        progress(f"Investigating question {item['id']}")
        # Result includes the answer, citations, trace, and citation audit.
        result = answer_question(
            item["question"], model, tools,
            max_tool_calls=args.max_tool_calls,
            max_model_turns=args.max_model_turns,
        )
        # Question calls counts only model turns used for this answer.
        question_calls = model_call_count(result.trace)
        online_model_calls += question_calls
        answers.append(
            {
                "id": item["id"],
                "question": item["question"],
                "answer": result.answer,
                "citations": result.citations,
                "citation_audit": result.audit,
                "online_model_calls": question_calls,
            }
        )
        # Markdown copies cited original lines without another model request.
        markdown = render_answer_markdown(
            item["question"], result.answer, result.citations, corpus,
            question_calls, result.audit,
        )
        # Stream writes one report per question without replacing prior output.
        with (reports / f"question-{number:03d}.md").open("x", encoding="utf-8") as stream:
            stream.write(markdown)
        trace.extend({**entry, "question_id": item["id"]} for entry in result.trace)
        progress(f"Completed question {item['id']}")
    _write_json(output / "answers.json", answers)
    # Stream writes the full ordered trace as one JSON object per line.
    with (output / "trace.jsonl").open("x", encoding="utf-8") as stream:
        # Entry is one recorded model, tool, or validation action.
        for entry in trace:
            stream.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    # Usage totals all recorded model tokens across preparation and answers.
    usage = {
        "input_tokens": sum(entry.get("usage", {}).get("input_tokens", 0) for entry in trace),
        "output_tokens": sum(entry.get("usage", {}).get("output_tokens", 0) for entry in trace),
    }
    _write_json(
        output / "run.json",
        {
            "provider": args.provider,
            "model": args.model,
            "extraction_model": snapshot.extraction_model,
            "documents": len(corpus.sources),
            "questions": len(answers),
            "model_calls": online_model_calls,
            "offline_model_calls": offline_model_calls,
            "total_model_calls": offline_model_calls + online_model_calls,
            "usage": usage,
            "runtime_seconds": round(time.monotonic() - started, 2),
            "source_hashes": corpus.manifest(),
            "snapshot_reused": bool(args.snapshot),
            "cache_enabled": args.reuse_cache,
            "cost_usd": None,
            "cost_note": "Provider billing rate was not supplied; token usage is recorded for independent costing.",
        },
    )
    progress("Review run complete")
    return output


def main() -> None:
    """Parse command-line options and print the new artifact directory."""
    # Parser defines the public command-line contract.
    parser = argparse.ArgumentParser(description="Auditable, source-grounded clinical record review")
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--questions", type=Path, help="JSON questions file, unless --prepare-only is used")
    parser.add_argument("--prepare-only", action="store_true", help="Build a fresh abstraction without asking questions yet")
    parser.add_argument("--output", type=Path, default=Path("runs"))
    parser.add_argument("--provider", choices=("anthropic", "openai"), default="openai")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--snapshot", type=Path, help="Reuse an abstraction only if every source hash matches")
    parser.add_argument("--reuse-cache", action="store_true", help="Reuse prior model-stage results from this output root")
    parser.add_argument("--start", help="Inclusive review start date, YYYY-MM-DD")
    parser.add_argument("--end", help="Inclusive review end date, YYYY-MM-DD")
    parser.add_argument("--batch-chars", type=int, default=13500)
    parser.add_argument("--max-tool-calls", type=int, default=12)
    parser.add_argument("--max-model-turns", type=int, default=6)
    # Args is the validated set of command-line options for one run.
    args = parser.parse_args()
    if args.prepare_only and args.questions:
        parser.error("--prepare-only and --questions cannot be used together")
    if not args.prepare_only and not args.questions:
        parser.error("--questions is required unless --prepare-only is used")
    # Target is the output directory printed for downstream scripts.
    target = run(args)
    print(target)


if __name__ == "__main__":
    main()
