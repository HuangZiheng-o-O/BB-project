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
from bb.models import ReviewSnapshot, validate_snapshot_reuse
from bb.report import model_call_count, render_answer_markdown
from bb.source import Corpus


def _new_directory(parent: Path) -> Path:
    """Give each session and answer an independent artifact directory."""
    parent.mkdir(parents=True, exist_ok=True)
    # Name combines UTC time with randomness to avoid output collisions.
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    # Target is the new directory owned by one session or answer.
    target = parent / name
    target.mkdir(exist_ok=False)
    return target


class ReviewSession:
    """Reuse one validated abstraction, calculation, source index, and model client."""

    def __init__(
        self,
        documents: Path,
        run_path: Path,
        output_root: Path,
        model: ModelPort,
        max_tool_calls: int = 12,
        max_model_turns: int = 6,
    ) -> None:
        """Validate source hashes, model identity, and saved calculation."""
        # Run metadata identifies the model that produced the preparation run.
        run_metadata = json.loads((run_path / "run.json").read_text(encoding="utf-8"))
        if run_metadata["model"] != model.model_name:
            raise ValueError("The selected run and answer model differ; use a run produced by this model")
        self.directory = _new_directory(output_root)
        self.corpus = Corpus(documents, self.directory / "index.sqlite3")
        self.snapshot = ReviewSnapshot.model_validate_json(
            (run_path / "abstraction.json").read_text(encoding="utf-8")
        )
        validate_snapshot_reuse(self.snapshot, model.model_name, self.corpus.manifest())
        # Recorded calculation is checked against a fresh deterministic result.
        recorded = json.loads((run_path / "calculation.json").read_text(encoding="utf-8"))
        # Period preserves the original inclusive review window.
        period = recorded["period"]
        # Recalculated totals detect stale snapshots or changed arithmetic.
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
        """Investigate one new question and save its report and trace."""
        # Clean question is the nonempty text submitted through the page.
        clean_question = (question or "").strip()
        if not clean_question:
            raise ValueError("Enter a question before submitting")
        # Started measures only this online investigation.
        started = time.monotonic()
        # Result contains the cited answer and its tool/model trace.
        result = answer_question(
            clean_question,
            self.model,
            self.tools,
            max_tool_calls=self.max_tool_calls,
            max_model_turns=self.max_model_turns,
        )
        # Online calls exclude the preparation run reused by this session.
        online_model_calls = model_call_count(result.trace)
        # Markdown includes the question, answer, and cited original lines.
        markdown = render_answer_markdown(
            clean_question, result.answer, result.citations, self.corpus,
            online_model_calls, result.audit,
        )

        # Every answer receives its own downloadable report and trace.
        answer_dir = _new_directory(self.directory / "answers")
        # Markdown path is also returned to Gradio for download.
        markdown_path = answer_dir / "answer.md"
        with markdown_path.open("x", encoding="utf-8") as stream:
            stream.write(markdown)
        with (answer_dir / "trace.jsonl").open("x", encoding="utf-8") as stream:
            # Item is one model or tool action from this answer run.
            for item in result.trace:
                stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
        # Usage sums model tokens for this question only.
        usage: dict[str, int] = {
            "input_tokens": sum(item.get("usage", {}).get("input_tokens", 0) for item in result.trace),
            "output_tokens": sum(item.get("usage", {}).get("output_tokens", 0) for item in result.trace),
        }
        # Metadata makes the saved answer independently auditable.
        metadata: dict[str, Any] = {
            "question": clean_question,
            "model": self.model.model_name,
            "citations": result.citations,
            "citation_audit": result.audit,
            "online_model_calls": online_model_calls,
            "usage": usage,
            "runtime_seconds": round(time.monotonic() - started, 2),
            "source_hashes": self.snapshot.source_hashes,
        }
        with (answer_dir / "run.json").open("x", encoding="utf-8") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        return markdown, str(markdown_path)


def build_app(session: ReviewSession):
    """Expose a single-question form and downloadable Markdown report."""
    import gradio as gr

    # App holds the controls for one question and one answer at a time.
    with gr.Blocks(title="Clinical Evidence Review") as app:
        gr.Markdown("# Clinical Evidence Review\nAsk a question about the loaded records.")
        # Question is the user's free-text input; submit starts investigation.
        question = gr.Textbox(label="Question", lines=3, placeholder="What does the record establish?")
        submit = gr.Button("Ask", variant="primary")
        # Answer renders Markdown; download exposes the same saved file.
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
    """Launch the local page against an existing preparation run."""
    # Parser defines the local page's command-line settings.
    parser = argparse.ArgumentParser(description="Local question-answer page for a saved clinical review")
    parser.add_argument("--documents", type=Path, default=Path("data"))
    parser.add_argument("--run", type=Path, required=True, help="Directory from a fresh bb-review run with the same model")
    parser.add_argument("--output", type=Path, default=Path("runs/web"))
    parser.add_argument("--provider", choices=("anthropic", "openai"), default="openai")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--port", type=int, default=7860)
    # Args selects the preparation run, provider, and local port.
    args = parser.parse_args()

    # Model and session are constructed once, then reused for new questions.
    model = make_model(args.provider, args.model, args.base_url)
    session = ReviewSession(args.documents, args.run, args.output, model)
    build_app(session).launch(server_name="127.0.0.1", server_port=args.port, share=False, show_error=True)


if __name__ == "__main__":
    main()
