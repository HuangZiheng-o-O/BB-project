"""Read-only source intake and line-addressable lexical search."""

from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from bb.models import Anchor


@dataclass(frozen=True)
class Source:
    """Immutable source text with a stable ID and content fingerprint."""

    source_id: str
    filename: str
    absolute_path: str
    sha256: str
    lines: tuple[str, ...]

    def formatted(self, first: int = 1, last: int | None = None) -> str:
        """Render one-based line labels used by extraction and citations."""
        # Clamp the requested end to the document's final line.
        last = min(last or len(self.lines), len(self.lines))
        # The body keeps original line text alongside stable citation labels.
        # Number is the one-based position of each original source line.
        body = "\n".join(
            f"L{number:04d} {self.lines[number - 1]}"
            for number in range(max(first, 1), last + 1)
        )
        return f"DOCUMENT {self.source_id} ({self.filename})\n{body}"


class Corpus:
    """Small implementation of the stable search/source port.

    A future search adapter can replace FTS5 without changing source anchors.
    """

    def __init__(self, documents: Path, index_path: Path) -> None:
        """Load trusted text files and create a per-run line-level search index."""
        self.documents = documents.resolve(strict=True)
        self.sources: dict[str, Source] = {}
        self.db = sqlite3.connect(index_path, check_same_thread=False)
        self._search_lock = threading.Lock()
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            "CREATE TABLE source (source_id TEXT PRIMARY KEY, filename TEXT NOT NULL, "
            "absolute_path TEXT NOT NULL, sha256 TEXT NOT NULL, line_count INTEGER NOT NULL)"
        )
        self.db.execute(
            "CREATE VIRTUAL TABLE source_fts USING fts5(source_id UNINDEXED, "
            "line_number UNINDEXED, content, tokenize='unicode61')"
        )
        self._load()

    def _load(self) -> None:
        """Reject escaping links, then preserve each file's original line order."""
        # Sorted paths make source ingestion and generated IDs reproducible.
        paths = sorted(self.documents.rglob("*.txt"))
        if not paths:
            raise ValueError(f"No .txt documents found in {self.documents}")
        # Path is each discovered text document under the corpus root.
        for path in paths:
            if path.is_symlink():
                raise ValueError(f"Symlink sources are not accepted: {path}")
            # Resolve again after the symlink check to enforce the corpus root.
            absolute = path.resolve(strict=True)
            if not absolute.is_relative_to(self.documents):
                raise ValueError(f"Source escaped document root: {path}")
            # Hash raw bytes so any source edit invalidates a saved snapshot.
            raw = absolute.read_bytes()
            # UTF-8 with an optional byte-order mark is the accepted input format.
            content = raw.decode("utf-8-sig")
            # Splitlines preserve the one-based positions used by citations.
            lines = tuple(content.splitlines())
            # Prefer the document's declared ID over its filename stem.
            match = re.search(r"^Document ID:\s*(\S+)", content, re.MULTILINE)
            # Source ID is the stable citation prefix for this document.
            source_id = match.group(1) if match else path.stem
            if source_id in self.sources:
                # The relative path disambiguates duplicate declared IDs.
                relative_name = str(absolute.relative_to(self.documents))
                source_id = f"{source_id}-{sha256(relative_name.encode()).hexdigest()[:8]}"
            # Keep the source metadata and text together for evidence lookup.
            source = Source(
                source_id=source_id,
                filename=str(absolute.relative_to(self.documents)),
                absolute_path=str(absolute),
                sha256=sha256(raw).hexdigest(),
                lines=lines,
            )
            self.sources[source_id] = source
            self.db.execute(
                "INSERT INTO source VALUES (?, ?, ?, ?, ?)",
                (source_id, source.filename, source.absolute_path, source.sha256, len(lines)),
            )
            self.db.executemany(
                "INSERT INTO source_fts (source_id, line_number, content) VALUES (?, ?, ?)",
                # Number and line preserve original positions in the FTS index.
                ((source_id, number, line) for number, line in enumerate(lines, 1)),
            )
        self.db.commit()

    def manifest(self) -> dict[str, str]:
        """Return fingerprints used to invalidate stale review snapshots."""
        # Each source ID maps to the hash of its original file bytes.
        return {source_id: source.sha256 for source_id, source in self.sources.items()}

    def get(self, source_id: str) -> Source:
        """Look up a source by its stable document identifier."""
        return self.sources[source_id]

    def validate_anchor(self, anchor: Anchor) -> None:
        """Ensure a model-supplied citation names existing source lines."""
        if anchor.source_id not in self.sources:
            raise ValueError(f"Unknown source: {anchor.source_id}")
        # The line count is the upper bound for every one-based citation.
        maximum = len(self.sources[anchor.source_id].lines)
        # Number is each line requested by the citation.
        if any(number > maximum for number in anchor.lines):
            raise ValueError(f"Line outside {anchor.source_id}: {anchor.lines}")

    def quote(self, anchor: Anchor) -> str:
        """Read the original text for a validated source anchor."""
        self.validate_anchor(anchor)
        # Read from the stored source, never from model-produced excerpts.
        source = self.get(anchor.source_id)
        # Number selects the exact original line in this source.
        return " ".join(source.lines[number - 1].strip() for number in anchor.lines)

    def open(self, source_id: str, first: int = 1, last: int | None = None) -> str:
        """Expose numbered original lines to the investigation agent."""
        # Resolve the source ID before formatting the requested window.
        source = self.get(source_id)
        return source.formatted(first, last)

    def search(self, query: str, limit: int = 15, source_ids: Iterable[str] | None = None) -> list[dict]:
        """Rank candidate lines; callers must use scan for exhaustive work."""
        # Use lexical tokens as candidate terms, not as a complete answer set.
        tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
        if not tokens:
            return []
        tokens = tokens[:12]
        # Quote terms so user punctuation cannot alter the FTS query structure.
        fts_query = " OR ".join(f'"{token}"' for token in tokens)
        # Optional source restriction is applied after SQLite ranking.
        permitted = set(source_ids) if source_ids is not None else None
        # Fetch extra rows before the Python-side optional source filter.
        with self._search_lock:
            # FTS scores order candidates; overfetch compensates for filtering.
            rows = self.db.execute(
                "SELECT source_id, line_number, content, bm25(source_fts) AS score "
                "FROM source_fts WHERE source_fts MATCH ? ORDER BY score LIMIT ?",
                (fts_query, min(max(limit * 8, limit), 500)),
            ).fetchall()
        # Return only the requested number of source-line candidates.
        results = []
        # Row is one ranked line returned by the FTS index.
        for row in rows:
            if permitted is not None and row["source_id"] not in permitted:
                continue
            results.append(
                {
                    "source_id": row["source_id"],
                    "line": int(row["line_number"]),
                    "text": row["content"],
                    "score": float(row["score"]),
                }
            )
            if len(results) == limit:
                break
        return results

    def extraction_batches(self, max_chars: int = 13500) -> list[str]:
        """Pack numbered sources into bounded model contexts without omissions."""
        # Completed batches are sent to independent model extraction calls.
        batches: list[str] = []
        # Pending parts share the next batch until its character budget is full.
        pending: list[str] = []
        # Current counts the characters already reserved in the pending batch.
        current = 0
        # Source is each complete document in deterministic ingestion order.
        for source in self.sources.values():
            # Oversized documents are divided on original line boundaries.
            parts = self._source_parts(source, max_chars)
            # Part is a numbered line window packed into the current batch.
            for part in parts:
                if pending and current + len(part) > max_chars:
                    batches.append("\n\n".join(pending))
                    pending, current = [], 0
                pending.append(part)
                current += len(part)
        if pending:
            batches.append("\n\n".join(pending))
        return batches

    @staticmethod
    def _source_parts(source: Source, max_chars: int) -> list[str]:
        """Split an oversized source on line boundaries to preserve anchors."""
        if len(source.formatted()) <= max_chars:
            return [source.formatted()]
        # Parts cover consecutive, nonoverlapping source-line windows.
        parts: list[str] = []
        # First is the one-based line where the next part begins.
        first = 1
        while first <= len(source.lines):
            # Last advances until the next line would exceed the budget.
            last = first
            # Size estimates content and line-label overhead for this part.
            size = 0
            while last <= len(source.lines) and size + len(source.lines[last - 1]) < max_chars - 200:
                size += len(source.lines[last - 1]) + 8
                last += 1
            last = max(first, last - 1)
            parts.append(source.formatted(first, last))
            first = last + 1
        return parts
