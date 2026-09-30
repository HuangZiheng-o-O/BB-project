"""Verify whether extracted clock intervals describe patient contact or service activity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from bb.cache import StageCache
from bb.model_provider import ModelPort, generate_json
from bb.models import AuditFinding, BatchExtraction
from bb.source import Corpus


TIME_SCOPE_SYSTEM = """Audit the provenance and scope of extracted clock intervals. Return one JSON object:
{"decisions":[{"mention_id":"...","patient_actual_supported":true|false|null,"reason":"..."}]}.

For EVERY supplied mention, determine whether its actual_intervals are explicitly supported as THIS PATIENT's actual arrival/departure or direct therapeutic contact in the original source. A group schedule, session opening/closing time, facilitator activity window, or session break does not by itself establish the patient's actual presence for that full period. Participation narrative without patient-specific clock times also does not establish full attendance. Conversely, explicit patient contact times do support actual_intervals. Read the full numbered source and distinguish its time fields by role. Use false when the clock spans describe only the service/group rather than the patient's own time; use null if genuinely unclear. Do not calculate therapy minutes or adjudicate other sources. Return JSON only."""


def audit_time_scope(
    extraction: BatchExtraction,
    corpus: Corpus,
    model: ModelPort,
    cache_dir: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[AuditFinding], list[dict[str, Any]]]:
    candidates = [
        mention for mention in extraction.events
        if mention.document_role == "clinical"
        and "group" in (mention.service_type or "").lower()
        and mention.actual_intervals
        and mention.scheduled_intervals
    ]
    if not candidates:
        return [], []
    if progress:
        progress(f"Auditing patient-time scope for {len(candidates)} clinical group mentions")
    payload = [
        {
            "mention_id": mention.mention_id,
            "source_id": mention.source_id,
            "extracted_actual_intervals": [item.model_dump() for item in mention.actual_intervals],
            "scheduled_intervals": [item.model_dump() for item in mention.scheduled_intervals],
            "source": corpus.get(mention.source_id).formatted(),
        }
        for mention in candidates
    ]
    serialized = json.dumps(payload, ensure_ascii=False)
    cache = StageCache(cache_dir) if cache_dir else None
    cache_path = cache.path("time_scope", model.model_name, TIME_SCOPE_SYSTEM, serialized) if cache else None
    result = cache.read(cache_path) if cache_path else None
    if result is None:
        result, calls = generate_json(
            model, TIME_SCOPE_SYSTEM,
            f"Audit these extracted time claims:\n{serialized}",
            max_tokens=2000,
        )
    else:
        calls = [{"cache_hit": True}]
    trace = [{**call, "stage": "time_scope"} for call in calls]
    decisions = result.get("decisions", [])
    by_id = {item.get("mention_id"): item for item in decisions if isinstance(item, dict)}
    expected = {mention.mention_id for mention in candidates}
    if set(by_id) != expected or len(decisions) != len(expected):
        raise ValueError("Time-scope audit did not return exactly one decision per candidate")
    findings: list[AuditFinding] = []
    for mention in candidates:
        decision = by_id[mention.mention_id]
        verdict = decision.get("patient_actual_supported")
        if verdict is False:
            original = [item.model_dump() for item in mention.actual_intervals]
            mention.actual_intervals = []
            findings.append(
                AuditFinding(
                    code="time_scope_reclassified",
                    detail=f"{mention.mention_id}: candidate patient intervals {original} were service-level time; {decision.get('reason', '')}",
                    source_refs=[mention.anchor().reference()],
                )
            )
        elif verdict is None:
            findings.append(
                AuditFinding(
                    code="time_scope_uncertain",
                    detail=f"{mention.mention_id}: patient-specific basis for extracted time remains unclear; {decision.get('reason', '')}",
                    source_refs=[mention.anchor().reference()],
                )
            )
        elif verdict is not True:
            raise ValueError("Time-scope verdict must be true, false, or null")
    if cache_path and not cache_path.exists():
        StageCache.write(cache_path, result)
    trace.append({"stage": "time_scope_decisions", "decisions": decisions})
    return findings, trace
