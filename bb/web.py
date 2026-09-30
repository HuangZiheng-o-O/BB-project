"""A small local Gradio page for asking one question at a time."""

from __future__ import annotations

import argparse
import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bb.agent import EvidenceTools, answer_question
from bb.compute import calculate_review
from bb.model_provider import ModelPort, make_model
from bb.models import ReviewSnapshot
from bb.source import Corpus


def _new_directory(parent: Path) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    target = parent / name
    target.mkdir(exist_ok=False)
    return target


class ReviewSession:
    """Reuse one validated abstraction, calculation, source index, and model client."""

    def __init__(
        self,
        documents: Path,
        snapshot_path: Path,
        calculation_path: Path,
        output_root: Path,
        model: ModelPort,
        max_tool_calls: int = 12,
        max_model_turns: int = 6,
    ) -> None:
        self.directory = _new_directory(output_root)
        self.corpus = Corpus(documents, self.directory / "index.sqlite3")
        self.snapshot = ReviewSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
        if self.snapshot.source_hashes != self.corpus.manifest():
            raise ValueError("Snapshot source hashes do not match the document directory")
        recorded = json.loads(calculation_path.read_text(encoding="utf-8"))
        period = recorded["period"]
        recalculated = calculate_review(
            self.snapshot.reconciliation,
            self.snapshot.extraction,
            period["start"],
            period["end"],
            findings=self.snapshot.findings,
        )
        if recalculated != recorded:
            raise ValueError("Calculation does not match the snapshot and current code")
        self.tools = EvidenceTools(self.corpus, self.snapshot, recalculated)
        self.model = model
        self.max_tool_calls = max_tool_calls
        self.max_model_turns = max_model_turns

    def ask(self, question: str) -> tuple[str, str]:
        clean_question = (question or "").strip()
        if not clean_question:
            raise ValueError("Enter a question before submitting")
        started = time.monotonic()
        result = answer_question(
            clean_question,
            self.model,
            self.tools,
            max_tool_calls=self.max_tool_calls,
            max_model_turns=self.max_model_turns,
        )
        markdown = f"# Question\n\n{clean_question}\n\n# Answer\n\n{result.answer.strip()}\n"
        if result.audit:
            markdown += "\n## Citation audit warnings\n\n"
            markdown += "\n".join(f"- {issue}" for issue in result.audit) + "\n"

        answer_dir = _new_directory(self.directory / "answers")
        markdown_path = answer_dir / "answer.md"
        with markdown_path.open("x", encoding="utf-8") as stream:
            stream.write(markdown)
        with (answer_dir / "trace.jsonl").open("x", encoding="utf-8") as stream:
            for item in result.trace:
                stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
        usage: dict[str, int] = {
            "input_tokens": sum(item.get("usage", {}).get("input_tokens", 0) for item in result.trace),
            "output_tokens": sum(item.get("usage", {}).get("output_tokens", 0) for item in result.trace),
        }
        metadata: dict[str, Any] = {
            "question": clean_question,
            "model": self.model.model_name,
            "citations": result.citations,
            "citation_audit": result.audit,
            "usage": usage,
            "runtime_seconds": round(time.monotonic() - started, 2),
            "source_hashes": self.snapshot.source_hashes,
        }
        with (answer_dir / "run.json").open("x", encoding="utf-8") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        return markdown, str(markdown_path)


def build_app(session: ReviewSession):
    import gradio as gr

    with gr.Blocks(title="Clinical Evidence Review") as app:
        gr.Markdown("# Clinical Evidence Review\nAsk a question about the loaded records.")
        question = gr.Textbox(label="Question", lines=3, placeholder="What does the record establish?")
        submit = gr.Button("Ask", variant="primary")
        answer = gr.Markdown(label="Answer")
        download = gr.File(label="Download Markdown", interactive=False)
        submit.click(
            fn=session.ask,
            inputs=question,
            outputs=[answer, download],
            concurrency_limit=1,
        )
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Local question-answer page for a saved clinical review")
    parser.add_argument("--documents", type=Path, default=Path("documents"))
    parser.add_argument("--snapshot", type=Path, default=Path("artifacts/development/abstraction.json"))
    parser.add_argument("--calculation", type=Path, default=Path("artifacts/development/calculation.json"))
    parser.add_argument("--output", type=Path, default=Path("runs/web"))
    parser.add_argument("--provider", choices=("anthropic", "openai"), default="openai")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    model = make_model(args.provider, args.model, args.base_url)
    session = ReviewSession(args.documents, args.snapshot, args.calculation, args.output, model)
    build_app(session).launch(server_name="127.0.0.1", server_port=args.port, share=False, show_error=True)


if __name__ == "__main__":
    main()
