"""Immutable, content-addressed model stage cache for repeatable long runs."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any


class StageCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def path(self, stage: str, model: str, prompt: str, payload: str) -> Path:
        key = json.dumps([stage, model, prompt, payload], ensure_ascii=False)
        digest = sha256(key.encode()).hexdigest()
        return self.directory / f"{stage}-{digest}.json"

    @staticmethod
    def read(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def write(path: Path, value: dict[str, Any]) -> None:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
