"""Bounded model repair for source-grounded stage output."""

from __future__ import annotations

import json
from typing import Any, Callable

from bb.model_provider import ModelPort, generate_json


class StageValidationError(ValueError):
    """A model stage remained invalid after feedback and fresh attempts."""


def generate_checked_json(
    model: ModelPort,
    system: str,
    source_prompt: str,
    validate: Callable[[dict[str, Any]], list[str]],
    *,
    max_tokens: int,
    attempts: int = 3,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a complete validated result, or stop before downstream stages use it.

    The validator owns domain rules. The repair loop only communicates errors and
    retries against the original evidence, so one question cannot change its rules.
    """
    trace: list[dict[str, Any]] = []
    feedback = ""
    for attempt in range(1, attempts + 1):
        prompt = source_prompt + feedback
        try:
            result, calls = generate_json(model, system, prompt, max_tokens=max_tokens)
        except ValueError as error:
            errors = [str(error)]
            result, calls = {}, []
        else:
            errors = validate(result)
        trace.extend({**call, "validation_attempt": attempt} for call in calls)
        trace.append({"stage": "validation", "validation_attempt": attempt, "errors": errors})
        if not errors:
            return result, trace
        # Feedback is derived from the stage validator, not from a particular question.
        previous = json.dumps(result, ensure_ascii=False)
        feedback = (
            "\n\nThe previous candidate failed validation. Re-read the original evidence "
            "and repair the candidate into a complete corrected JSON object. Do not omit valid claims "
            "or invent missing evidence. Validation errors:\n"
            + json.dumps(errors[:30], ensure_ascii=False)
            + (f"\nAdditional errors: {len(errors) - 30}." if len(errors) > 30 else "")
            + (f"\nPrevious candidate:\n{previous}" if len(previous) <= 30000 else "")
        )
    raise StageValidationError(
        f"Model stage failed validation after {attempts} attempts: "
        + "; ".join(errors[:5])
    )
