"""Immutable, content-addressed model stage cache for repeatable long runs."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any


class StageCache:
    """Store validated stage outputs under content-derived file names."""

    def __init__(self, directory: Path) -> None:
        """Create the shared cache directory when caching is enabled."""
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def path(self, stage: str, model: str, prompt: str, payload: str) -> Path:
        """Include the model and exact inputs so stale results miss the cache."""
        key = json.dumps([stage, model, prompt, payload], ensure_ascii=False)
        digest = sha256(key.encode()).hexdigest()
        return self.directory / f"{stage}-{digest}.json"

    @staticmethod
    def read(path: Path) -> dict[str, Any] | None:
        """Treat absent or malformed entries as misses for safe recovery."""
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def write(path: Path, value: dict[str, Any]) -> None:
        """Create an immutable cache entry without replacing earlier output."""
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
