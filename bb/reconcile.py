"""Reconcile source mentions into reviewable, field-level event decisions."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from pydantic import ValidationError

from bb.model_provider import ModelPort, generate_json
from bb.models import AuditFinding, BatchExtraction, EventMention, Reconciliation, ResolvedEvent
from bb.source import Corpus


RECONCILIATION_SYSTEM = """You reconcile claims about clinical encounters, not documents. Return one JSON object:
{"events":[{"event_id":"...","service_date":"YYYY-MM-DD or null","service_type":"...","disposition":"delivered|not_delivered|uncertain","patient_therapy":"yes|no|uncertain","interval_options":[[{"start":"HH:MM","end":"HH:MM"}]],"excluded_intervals":[{"start":"HH:MM","end":"HH:MM"}],"supporting_mentions":["id"],"opposing_mentions":["id"],"decision_notes":"..."}],"unresolved_mention_ids":[]}.

Produce exactly one event for EVERY supplied group_id, using that group_id as event_id. Include non-therapy encounters and no-shows as events too. Put EVERY supplied mention ID in supporting_mentions or opposing_mentions, exactly once, and explain important inclusion/exclusion decisions. These lists mean considered evidence for or against the chosen event decision, not a document credibility ranking. A clinical note, attendance row, billing record, draft, and later correction can refer to the same encounter, not separate visits. A source received later does not automatically prevail.

For delivered patient psychotherapy, interval_options contains one or more POSSIBLE sets of patient-present time spans. One unambiguous event has one option. If two credible patient-contact records conflict without an explicit amendment, preserve each plausible option rather than choosing or adding them. If no patient therapy occurred, interval_options must be empty.

Group breaks, network disconnects, and partner-only segments cannot count as patient therapy. Put shared breaks/disconnections in excluded_intervals if they overlap a broad patient interval. If actual_intervals already exclude a gap, retaining the gap in excluded_intervals is harmless. For a mixed family encounter, use only the patient's portion.

An explicit correction supersedes ONLY the named field for that earlier event. A later retransmission of the original record does not undo the correction and does not create a new event. A schedule, charge, authorization, unsigned template, or administrative contact alone does not establish that patient therapy was delivered. Signed but conflicting clinical records may leave duration unresolved.

Do not calculate minutes or weekly totals. If evidence cannot establish delivery or patient presence, set uncertain and state why. Preserve concrete, source-grounded distinctions; do not silently resolve a conflict with a universal document priority rule. Return JSON only."""


def group_mentions(extraction: BatchExtraction) -> dict[str, list[EventMention]]:
    groups: dict[str, list[EventMention]] = defaultdict(list)
    known_patients = {item.patient_id for item in extraction.events if item.patient_id}
    sole_patient = next(iter(known_patients)) if len(known_patients) == 1 else None
    appointment_to_encounter: dict[tuple[str, str], set[str]] = defaultdict(set)
    for mention in extraction.events:
        patient = mention.patient_id or sole_patient
        if patient and mention.appointment_id and mention.encounter_id:
            appointment_to_encounter[(patient, mention.appointment_id)].add(mention.encounter_id)
    for mention in extraction.events:
        patient = mention.patient_id or sole_patient or f"unknown:{mention.source_id}"
        if mention.encounter_id:
            identity = mention.encounter_id
        elif mention.appointment_id:
            linked = appointment_to_encounter.get((patient, mention.appointment_id), set())
            identity = next(iter(linked)) if len(linked) == 1 else mention.appointment_id
        else:
            # A missing identity is kept separate rather than merged by date alone.
            identity = f"unlinked:{mention.mention_id}"
        key = f"{patient}:{identity}"
        groups[key].append(mention)
    return dict(groups)


def _group_payload(group_id: str, mentions: list[EventMention], corpus: Corpus) -> dict[str, Any]:
    payload = []
    for mention in mentions:
        data = mention.model_dump(exclude={"note"}, exclude_none=True)
        data["source_excerpt"] = corpus.quote(mention.anchor())[:1200]
        if mention.note:
            data["note"] = mention.note[:500]
        payload.append(data)
    return {"group_id": group_id, "mentions": payload}


def _batches(groups: dict[str, list[EventMention]], corpus: Corpus, max_chars: int = 18000) -> list[list[dict]]:
    output: list[list[dict]] = []
    pending: list[dict] = []
    length = 0
    for group_id, mentions in groups.items():
        item = _group_payload(group_id, mentions, corpus)
        item_length = len(json.dumps(item, ensure_ascii=False))
        if pending and length + item_length > max_chars:
            output.append(pending)
            pending, length = [], 0
        pending.append(item)
        length += item_length
    if pending:
        output.append(pending)
    return output


def reconcile_events(
    extraction: BatchExtraction,
    corpus: Corpus,
    model: ModelPort,
) -> tuple[Reconciliation, list[AuditFinding], list[dict[str, Any]]]:
    groups = group_mentions(extraction)
    findings: list[AuditFinding] = []
    trace: list[dict[str, Any]] = []
    resolved: dict[str, ResolvedEvent] = {}
    batches = _batches(groups, corpus)
    for number, batch in enumerate(batches, 1):
        expected = {item["group_id"] for item in batch}
        prompt = f"Reconcile group batch {number}/{len(batches)}:\n{json.dumps(batch, ensure_ascii=False)}"
        accepted: dict[str, ResolvedEvent] = {}
        errors: list[str] = []
        for attempt in range(2):
            data, calls = generate_json(model, RECONCILIATION_SYSTEM, prompt, max_tokens=10000)
            trace.extend({**call, "stage": "reconcile", "batch": number, "validation_attempt": attempt + 1} for call in calls)
            accepted, errors = {}, []
            for index, raw in enumerate(data.get("events", [])):
                try:
                    event = ResolvedEvent.model_validate(raw)
                    if event.event_id not in expected:
                        raise ValueError(f"Unknown group ID {event.event_id}")
                    member_ids = {mention.mention_id for mention in groups[event.event_id]}
                    listed_ids = event.supporting_mentions + event.opposing_mentions
                    if set(listed_ids) != member_ids or len(listed_ids) != len(member_ids):
                        raise ValueError("Decision must classify every mention exactly once")
                    if event.disposition == "not_delivered" and event.patient_therapy == "yes":
                        raise ValueError("Non-delivered event cannot be confirmed patient therapy")
                    if event.event_id in accepted:
                        raise ValueError("Duplicate decision for one event group")
                    accepted[event.event_id] = event
                except (ValidationError, ValueError, KeyError) as error:
                    errors.append(f"event {index}: {error}")
            missing = expected - set(accepted)
            if not errors and not missing:
                break
            prompt += f"\n\nPrevious response failed validation: {errors}; missing group IDs: {sorted(missing)}. Return all groups again, complete and corrected."
        for event in accepted.values():
            if event.patient_therapy == "yes" and not event.interval_options:
                findings.append(
                    AuditFinding(
                        code="unquantified_event",
                        detail=f"Patient therapy is claimed without a sourced interval for {event.event_id}",
                        source_refs=[mention.anchor().reference() for mention in groups[event.event_id]],
                    )
                )
        resolved.update(accepted)
        for error in errors:
            findings.append(AuditFinding(code="invalid_event_decision", detail=f"batch {number}: {error}"))
        if missing:
            findings.append(
                AuditFinding(
                    code="unresolved_event_group",
                    detail=f"Model omitted or invalidated groups: {', '.join(sorted(missing))}",
                )
            )
    unresolved = [
        mention.mention_id
        for group_id, mentions in groups.items()
        if group_id not in resolved
        for mention in mentions
    ]
    return Reconciliation(events=list(resolved.values()), unresolved_mention_ids=unresolved), findings, trace
