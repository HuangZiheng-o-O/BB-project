"""Deterministic question, answer, and source-evidence Markdown reports."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from bb.models import Anchor
from bb.source import Corpus


def model_call_count(trace: list[dict[str, Any]]) -> int:
    """Count model turns in one stage trace; tool executions have no usage entry."""
    # Entry is one trace action; only model actions carry token usage.
    return sum("usage" in entry for entry in trace)


def _cited_lines(citations: list[str], corpus: Corpus) -> dict[str, set[int]]:
    """Validate citations and group original line numbers by source."""
    # Grouped deduplicates lines when the answer cites a source repeatedly.
    grouped: dict[str, set[int]] = defaultdict(set)
    for reference in citations:
        # Source ID and suffix separate the document from its line labels.
        source_id, separator, suffix = reference.partition(":")
        if not separator:
            raise ValueError(f"Invalid source citation: {reference}")
        # Numbers expands every cited range into individual original lines.
        numbers: list[int] = []
        for part in suffix.split(","):
            # Match accepts a single line or an inclusive line range.
            match = re.fullmatch(r"L(\d+)(?:[-–]L(\d+))?", part)
            if not match:
                raise ValueError(f"Invalid source citation: {reference}")
            # First and last bound the source lines copied into the report.
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
    # Sections assemble the human-readable report in stable order.
    sections = [
        "# Question", "", question.strip(), "",
        "# Answer", "", answer.strip(), "",
        "# Evidence", "",
        "Original document lines referenced in the answer:", "",
    ]
    # Grouped links each cited source to its validated original line numbers.
    grouped = _cited_lines(citations, corpus)
    if not grouped:
        sections.extend(["No validated source lines were cited.", ""])
    # Source ID and numbers identify the original evidence lines to copy.
    for source_id, numbers in sorted(grouped.items()):
        # Source supplies the filename, local path, and verbatim evidence text.
        source = corpus.get(source_id)
        sections.extend([f"## {source_id} — [{source.filename}](<{source.absolute_path}>)", "", "```text"])
        sections.extend(f"L{number:04d} {source.lines[number - 1]}" for number in sorted(numbers))
        sections.extend(["```", ""])
    if citation_audit:
        sections.extend(["# Citation audit warnings", ""])
        # Warning is one unresolved citation problem shown in the report.
        sections.extend(f"- {warning}" for warning in citation_audit)
        sections.append("")
    sections.extend(["# Run information", "", f"- Online model calls: {online_model_calls}", ""])
    return "\n".join(sections)
