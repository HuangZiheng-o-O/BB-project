"""Deterministic question, answer, and source-evidence Markdown reports."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from bb.models import Anchor
from bb.source import Corpus


def model_call_count(trace: list[dict[str, Any]]) -> int:
    """Count model turns in one stage trace; tool executions have no usage entry."""
    return sum("usage" in entry for entry in trace)


def _cited_lines(citations: list[str], corpus: Corpus) -> dict[str, set[int]]:
    grouped: dict[str, set[int]] = defaultdict(set)
    for reference in citations:
        source_id, separator, suffix = reference.partition(":")
        if not separator:
            raise ValueError(f"Invalid source citation: {reference}")
        numbers: list[int] = []
        for part in suffix.split(","):
            match = re.fullmatch(r"L(\d+)(?:[-–]L(\d+))?", part)
            if not match:
                raise ValueError(f"Invalid source citation: {reference}")
            first = int(match.group(1))
            last = int(match.group(2)) if match.group(2) else first
            if last < first:
                raise ValueError(f"Invalid source citation: {reference}")
            numbers.extend(range(first, last + 1))
        corpus.validate_anchor(Anchor(source_id=source_id, lines=numbers))
        grouped[source_id].update(numbers)
    return grouped


def render_answer_markdown(
    question: str,
    answer: str,
    citations: list[str],
    corpus: Corpus,
    online_model_calls: int,
    citation_audit: list[str] | None = None,
) -> str:
    """Copy cited original lines locally, without another model call."""
    sections = [
        "# Question", "", question.strip(), "",
        "# Answer", "", answer.strip(), "",
        "# Evidence", "",
        "Original document lines referenced in the answer:", "",
    ]
    grouped = _cited_lines(citations, corpus)
    if not grouped:
        sections.extend(["No validated source lines were cited.", ""])
    for source_id, numbers in sorted(grouped.items()):
        source = corpus.get(source_id)
        sections.extend([f"## {source_id} — [{source.filename}](<{source.absolute_path}>)", "", "```text"])
        sections.extend(f"L{number:04d} {source.lines[number - 1]}" for number in sorted(numbers))
        sections.extend(["```", ""])
    if citation_audit:
        sections.extend(["# Citation audit warnings", ""])
        sections.extend(f"- {warning}" for warning in citation_audit)
        sections.append("")
    sections.extend(["# Run information", "", f"- Online model calls: {online_model_calls}", ""])
    return "\n".join(sections)
