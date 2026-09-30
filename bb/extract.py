"""Source-anchored candidate extraction; no answer-specific parsing rules."""

from __future__ import annotations

import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from bb.model_provider import ModelPort, generate_json
from bb.models import AuditFinding, BatchExtraction, EventMention, MeasureMention, Observation, PlanGoal
from bb.source import Corpus


EXTRACTION_SYSTEM = """You are a clinical records evidence extractor. Produce source claims, never a final patient answer.

Return one JSON object with exactly four arrays: events, goals, measures, observations. No markdown.
Every item MUST cite the provided DOCUMENT source_id and 1-based L-line numbers. Cite concise decisive lines (at most 12 per item). Do not invent a source or a line.

events: one mention per specific patient encounter or appointment described by each source. A multi-row register yields one mention per row. Fields: source_id, lines, patient_id (stable chart/MRN identifier if stated), encounter_id, appointment_id, service_date (YYYY-MM-DD), service_type (individual/group/family/medication/collateral/care_coordination/other), document_role (clinical/attendance/schedule/correction/charge/draft/administrative), status (delivered/attended/no_show/cancelled/scheduled/posted/draft/correction/unknown), patient_present (true/false/null), actual_intervals, scheduled_intervals, nontherapy_intervals, correction_field, correction_value, duplicate_of, note. Each interval is {start:"HH:MM",end:"HH:MM"}. Empty arrays and nulls are allowed.
actual_intervals represent documented patient-present clinical contact only. If a record reports only scheduled time, put it in scheduled_intervals. For a mixed family session, actual_intervals include only the patient's portion. A connection interruption or group break belongs in nontherapy_intervals; separate connection segments in one appointment remain one mention. A correction is a statement about an earlier field, not another service. A charge, unsigned template, authorization, or administrative call does not prove delivered patient therapy.

goals: signed treatment-plan participation goals only. Fields: source_id, lines, effective_from, effective_to, period, minimum_days, minimum_minutes, included_services, excluded_services, description. Leave unknown fields null. Do not infer targets from an authorization quantity.

measures: one mention per actual questionnaire or explicitly identified copy. Fields: source_id, lines, instrument, form_id, completed_date, score, copied_from_form, note. The receipt/import date is not a new completion date.

observations: concise patient-specific symptom, functional course, safety, treatment-change, or reason-for-extra-contact claims. Fields: source_id, lines, date, subject, theme, statement, polarity (positive/negative/uncertain/planned). Preserve who reported the observation and whether it is a plan rather than an achieved result in statement. Do not convert collateral observations into direct patient reports. Prefer a few important observations per source over generic repetition.

Extract all concrete encounters/appointment rows even when they are not therapy. Keep conflicting claims from different sources. Do not decide which source wins and do not calculate weekly totals."""


T = TypeVar("T", bound=BaseModel)


def _validated_items(
    data: dict[str, Any],
    key: str,
    model_type: type[T],
    corpus: Corpus,
    allowed_sources: set[str],
    findings: list[AuditFinding],
) -> list[T]:
    values = data.get(key, [])
    if not isinstance(values, list):
        findings.append(AuditFinding(code="invalid_extraction_array", detail=f"{key} is not a list"))
        return []
    valid: list[T] = []
    for index, raw in enumerate(values):
        try:
            item = model_type.model_validate(raw)
            anchor = item.anchor()
            if anchor.source_id not in allowed_sources:
                raise ValueError(f"{anchor.source_id} was not in this extraction batch")
            corpus.validate_anchor(anchor)
            if isinstance(item, EventMention):
                item.finalize_id()
            valid.append(item)
        except (ValueError, ValidationError, KeyError) as error:
            findings.append(
                AuditFinding(
                    code="invalid_source_candidate",
                    detail=f"{key}[{index}] rejected: {error}",
                )
            )
    return valid


def extract_corpus(
    corpus: Corpus,
    model: ModelPort,
    max_chars: int = 13500,
) -> tuple[BatchExtraction, list[AuditFinding], list[dict[str, Any]]]:
    all_events: list[EventMention] = []
    all_goals: list[PlanGoal] = []
    all_measures: list[MeasureMention] = []
    all_observations: list[Observation] = []
    findings: list[AuditFinding] = []
    trace: list[dict[str, Any]] = []
    batches = corpus.extraction_batches(max_chars=max_chars)
    for batch_number, batch in enumerate(batches, 1):
        allowed = set(re.findall(r"^DOCUMENT (\S+)", batch, re.MULTILINE))
        result, calls = generate_json(
            model,
            EXTRACTION_SYSTEM,
            f"Extract evidence from source batch {batch_number}/{len(batches)}:\n\n{batch}",
            max_tokens=10000,
        )
        trace.extend({**call, "stage": "extract", "batch": batch_number} for call in calls)
        all_events.extend(_validated_items(result, "events", EventMention, corpus, allowed, findings))
        all_goals.extend(_validated_items(result, "goals", PlanGoal, corpus, allowed, findings))
        all_measures.extend(_validated_items(result, "measures", MeasureMention, corpus, allowed, findings))
        all_observations.extend(
            _validated_items(result, "observations", Observation, corpus, allowed, findings)
        )
    unique_events = {item.mention_id: item for item in all_events}
    extraction = BatchExtraction(
        events=list(unique_events.values()),
        goals=all_goals,
        measures=all_measures,
        observations=all_observations,
    )
    return extraction, findings, trace
