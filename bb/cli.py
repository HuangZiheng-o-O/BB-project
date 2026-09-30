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
from bb.models import ReviewSnapshot
from bb.reconcile import reconcile_events
from bb.source import Corpus
from bb.time_audit import audit_time_scope


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


def _read_questions(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Questions file must contain a JSON array")
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
    parent.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    target = parent / name
    target.mkdir(exist_ok=False)
    return target


def run(args: argparse.Namespace) -> Path:
    started = time.monotonic()
    output = _run_directory(args.output)

    def progress(message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        print(f"[{timestamp}] {message}", file=sys.stderr, flush=True)

    progress("Indexing source documents")
    corpus = Corpus(args.documents, output / "index.sqlite3")
    model = make_model(args.provider, args.model, args.base_url)
    trace: list[dict[str, Any]] = []
    if args.snapshot:
        progress("Validating reusable abstraction")
        snapshot = ReviewSnapshot.model_validate_json(args.snapshot.read_text(encoding="utf-8"))
        if snapshot.source_hashes != corpus.manifest():
            raise ValueError("Snapshot source hashes do not match the current document directory")
    else:
        cache_dir = args.output / "_stage_cache" if args.reuse_cache else None
        extraction, findings, extraction_trace = extract_corpus(
            corpus, model, max_chars=args.batch_chars,
            cache_dir=cache_dir, progress=progress,
        )
        trace.extend(extraction_trace)
        time_findings, time_trace = audit_time_scope(
            extraction, corpus, model, cache_dir=cache_dir, progress=progress,
        )
        findings.extend(time_findings)
        trace.extend(time_trace)
        reconciliation, more_findings, reconciliation_trace = reconcile_events(
            extraction, corpus, model, cache_dir=cache_dir, progress=progress,
        )
        trace.extend(reconciliation_trace)
        snapshot = ReviewSnapshot(
            source_hashes=corpus.manifest(),
            extraction_model=args.model,
            extraction=extraction,
            reconciliation=reconciliation,
            findings=findings + more_findings,
        )
    _write_json(output / "abstraction.json", snapshot.model_dump())
    progress("Calculating event and weekly totals")
    calculation = calculate_review(
        snapshot.reconciliation, snapshot.extraction, args.start, args.end, findings=snapshot.findings,
    )
    _write_json(output / "calculation.json", calculation)
    tools = EvidenceTools(corpus, snapshot, calculation)
    answers: list[dict[str, Any]] = []
    questions = [] if args.prepare_only else _read_questions(args.questions)
    for item in questions:
        progress(f"Investigating question {item['id']}")
        result = answer_question(
            item["question"], model, tools,
            max_tool_calls=args.max_tool_calls,
            max_model_turns=args.max_model_turns,
        )
        answers.append(
            {
                "id": item["id"],
                "question": item["question"],
                "answer": result.answer,
                "citations": result.citations,
                "citation_audit": result.audit,
            }
        )
        trace.extend({**entry, "question_id": item["id"]} for entry in result.trace)
        progress(f"Completed question {item['id']}")
    _write_json(output / "answers.json", answers)
    with (output / "trace.jsonl").open("x", encoding="utf-8") as stream:
        for entry in trace:
            stream.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
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
            "model_calls": sum(entry.get("usage") is not None for entry in trace),
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
    args = parser.parse_args()
    if args.prepare_only and args.questions:
        parser.error("--prepare-only and --questions cannot be used together")
    if not args.prepare_only and not args.questions:
        parser.error("--questions is required unless --prepare-only is used")
    target = run(args)
    print(target)


if __name__ == "__main__":
    main()
