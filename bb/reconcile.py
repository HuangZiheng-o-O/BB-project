"""Reconcile source mentions into reviewable, field-level event decisions."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from bb.cache import StageCache
from bb.model_provider import ModelPort
from bb.models import AuditFinding, BatchExtraction, EventMention, Reconciliation, ResolvedEvent
from bb.repair import generate_checked_json
from bb.source import Corpus


RECONCILIATION_SYSTEM = """You reconcile claims about clinical encounters, not documents. Return one JSON object:
{"events":[{"event_id":"...","service_date":"YYYY-MM-DD or null","service_type":"...","disposition":"delivered|not_delivered|uncertain","patient_therapy":"yes|no|uncertain","interval_options":[[{"start":"HH:MM","end":"HH:MM"}]],"excluded_intervals":[{"start":"HH:MM","end":"HH:MM"}],"supporting_mentions":["id"],"opposing_mentions":["id"],"decision_notes":"..."}],"unresolved_mention_ids":[]}.

Produce exactly one event for EVERY supplied group_id, using that group_id as event_id. Include non-therapy encounters and no-shows as events too. Put EVERY supplied mention ID in supporting_mentions or opposing_mentions, exactly once, and explain important inclusion/exclusion decisions. These lists mean considered evidence for or against the chosen event decision, not a document credibility ranking. A clinical note, attendance row, billing record, draft, and later correction can refer to the same encounter, not separate visits. A source received later does not automatically prevail.

For delivered patient psychotherapy, interval_options contains one or more POSSIBLE sets of patient-present time spans. One unambiguous event has one option. If two credible patient-contact records conflict without an explicit amendment, preserve each plausible option rather than choosing or adding them. If no patient therapy occurred, interval_options must be empty.

Group breaks, network disconnects, and partner-only segments cannot count as patient therapy. Put shared breaks/disconnections in excluded_intervals if they overlap a broad patient interval. If actual_intervals already exclude a gap, retaining the gap in excluded_intervals is harmless. For a mixed family encounter, use only the patient's portion.

An explicit correction supersedes ONLY the named field for that earlier event. A later retransmission of the original record does not undo the correction and does not create a new event. A schedule, charge, authorization, unsigned template, or administrative contact alone does not establish that patient therapy was delivered. Signed but conflicting clinical records may leave duration unresolved.

Do not calculate minutes or weekly totals. If evidence cannot establish delivery or patient presence, set uncertain and state why. Preserve concrete, source-grounded distinctions; do not silently resolve a conflict with a universal document priority rule. Return JSON only."""

RECONCILIATION_CACHE_VERSION = "clinical-interval-conflict-v2"


def group_mentions(extraction: BatchExtraction) -> dict[str, list[EventMention]]:
    """Group claims by patient and encounter, linking unique appointment IDs."""
    # Groups will contain every source claim for one patient encounter.
    groups: dict[str, list[EventMention]] = defaultdict(list)
    # A sole known patient can safely fill absent patient IDs in related records.
    known_patients = {item.patient_id for item in extraction.events if item.patient_id}
    # Sole patient is used only when the corpus names exactly one patient.
    sole_patient = next(iter(known_patients)) if len(known_patients) == 1 else None
    # Appointment-to-encounter links are scoped to the patient.
    appointment_to_encounter: dict[tuple[str, str], set[str]] = defaultdict(set)
    # Mention is each extracted encounter claim being indexed by appointment.
    for mention in extraction.events:
        # Patient is the explicit ID or the only patient represented in this corpus.
        patient = mention.patient_id or sole_patient
        if patient and mention.appointment_id and mention.encounter_id:
            appointment_to_encounter[(patient, mention.appointment_id)].add(mention.encounter_id)
    for mention in extraction.events:
        # Unknown patients remain source-scoped to avoid accidental merging.
        patient = mention.patient_id or sole_patient or f"unknown:{mention.source_id}"
        if mention.encounter_id:
            # Prefer an explicit encounter ID as the event identity.
            identity = mention.encounter_id
        elif mention.appointment_id:
            # Link an appointment only when it maps to exactly one encounter.
            linked = appointment_to_encounter.get((patient, mention.appointment_id), set())
            identity = next(iter(linked)) if len(linked) == 1 else mention.appointment_id
        else:
            # A missing identity is kept separate rather than merged by date alone.
            identity = f"unlinked:{mention.mention_id}"
        # Key combines patient and event identity for collision-free grouping.
        key = f"{patient}:{identity}"
        groups[key].append(mention)
    return dict(groups)


def _group_payload(group_id: str, mentions: list[EventMention], corpus: Corpus) -> dict[str, Any]:
    """Attach concise original excerpts to every claim in a group."""
    # Payload contains source-backed claims submitted together for one decision.
    payload = []
    for mention in mentions:
        # Data omits empty optional fields but retains provenance and status.
        data = mention.model_dump(exclude={"note"}, exclude_none=True)
        data["source_excerpt"] = corpus.quote(mention.anchor())[:1200]
        if mention.note:
            data["note"] = mention.note[:500]
        payload.append(data)
    return {"group_id": group_id, "mentions": payload}


def _batches(groups: dict[str, list[EventMention]], corpus: Corpus, max_chars: int = 18000) -> list[list[dict]]:
    """Pack complete encounter groups without splitting their evidence."""
    # Output contains completed model batches; pending is the current batch.
    output: list[list[dict]] = []
    # Pending holds complete encounter payloads awaiting submission.
    pending: list[dict] = []
    # Length tracks the serialized size of pending group payloads.
    length = 0
    for group_id, mentions in groups.items():
        # Item keeps all competing mentions of one encounter together.
        item = _group_payload(group_id, mentions, corpus)
        # Item length determines whether this group starts a new batch.
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
    cache_dir: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[Reconciliation, list[AuditFinding], list[dict[str, Any]]]:
    """Resolve each encounter while retaining supported conflicts.

    Args:
        extraction: Validated source claims from the offline stage.
        corpus: Original lines used to substantiate each claim.
        model: Provider-neutral model used for decision and repair turns.
        cache_dir: Optional directory for content-addressed decisions.
        progress: Optional callback for stage progress messages.

    Returns:
        Encounter decisions, audit findings, and model-call trace entries.
    """
    # Groups connect source mentions before the model judges any encounter.
    groups = group_mentions(extraction)
    # Findings records unresolved duration facts; trace records model attempts.
    findings: list[AuditFinding] = []
    # Trace retains reconciliation attempts and any repair feedback.
    trace: list[dict[str, Any]] = []
    # Resolved maps each group ID to its validated event decision.
    resolved: dict[str, ResolvedEvent] = {}
    # Batches bound model context while preserving whole encounter groups.
    batches = _batches(groups, corpus)
    # Cached decisions are reused only if they still pass current checks.
    cache = StageCache(cache_dir) if cache_dir else None
    # Number and batch identify one bounded set of encounter groups.
    for number, batch in enumerate(batches, 1):
        if progress:
            progress(f"Reconciling batch {number}/{len(batches)}")
        # Expected IDs require a decision for every group in this batch.
        expected = {item["group_id"] for item in batch}
        # Prompt contains all source-backed claims for these groups.
        prompt = f"Reconcile group batch {number}/{len(batches)}:\n{json.dumps(batch, ensure_ascii=False)}"
        # Cache key includes an explicit version of the decision contract.
        cache_path = cache.path(
            "reconcile", model.model_name, RECONCILIATION_SYSTEM + RECONCILIATION_CACHE_VERSION, prompt,
        ) if cache else None
        def validated_events(data: dict[str, Any]) -> tuple[dict[str, ResolvedEvent], list[str]]:
            """Require complete mention coverage and explicit interval options."""
            # Accepted holds decisions that pass schema and evidence checks.
            accepted: dict[str, ResolvedEvent] = {}
            # Errors feeds the generic repair loop with precise failures.
            errors: list[str] = []
            # Rows is the model's proposed event-decision array.
            rows = data.get("events")
            if not isinstance(rows, list):
                return {}, ["events must be an array"]
            # Index locates a bad row; raw is the proposed event payload.
            for index, raw in enumerate(rows):
                try:
                    # Event is one typed proposed decision for a known group.
                    event = ResolvedEvent.model_validate(raw)
                    if event.event_id not in expected:
                        raise ValueError(f"Unknown group ID {event.event_id}")
                    # Member IDs define the exact evidence set to classify.
                    member_ids = {mention.mention_id for mention in groups[event.event_id]}
                    # Listed IDs must name each member once, on either side.
                    listed_ids = event.supporting_mentions + event.opposing_mentions
                    if set(listed_ids) != member_ids or len(listed_ids) != len(member_ids):
                        raise ValueError("Decision must classify every mention exactly once")
                    if event.disposition == "not_delivered" and event.patient_therapy == "yes":
                        raise ValueError("Non-delivered event cannot be confirmed patient therapy")
                    # Members provide the original patient-time claims.
                    members = groups[event.event_id]
                    # Clinical intervals form alternatives when signed claims conflict.
                    clinical_intervals = {
                        tuple((span.start, span.end) for span in mention.actual_intervals)
                        for mention in members
                        if mention.document_role == "clinical"
                        and mention.patient_present is True
                        and mention.actual_intervals
                    }
                    # A named correction can replace the corrected field's old value.
                    explicit_correction = any(mention.correction_field for mention in members)
                    if len(clinical_intervals) > 1 and not explicit_correction:
                        # Chosen intervals must preserve every uncorrected alternative.
                        chosen_intervals = {
                            tuple((span.start, span.end) for span in option)
                            for option in event.interval_options
                        }
                        if not clinical_intervals.issubset(chosen_intervals):
                            raise ValueError(
                                "Conflicting clinical patient-contact intervals require separate interval_options"
                            )
                    if event.event_id in accepted:
                        raise ValueError("Duplicate decision for one event group")
                    accepted[event.event_id] = event
                except (ValidationError, ValueError, KeyError) as error:
                    errors.append(f"event {index}: {error}")
            # Missing group IDs signal incomplete model output.
            missing = expected - set(accepted)
            if missing:
                errors.append(f"Missing group IDs: {sorted(missing)}")
            return accepted, errors

        # Cached is a prior candidate, never accepted without validation.
        cached = cache.read(cache_path) if cache_path else None
        # Never reuse a decision that fails today's reconciliation contract.
        if cached is not None and validated_events(cached)[1]:
            cached = None
        if cached is None:
            # Data is the fresh validated decision set; calls records retries.
            data, calls = generate_checked_json(
                model, RECONCILIATION_SYSTEM, prompt,
                lambda value: validated_events(value)[1], max_tokens=10000,
            )
        else:
            data, calls = cached, [{"cache_hit": True}]
        # Call is each model attempt associated with this reconciliation batch.
        trace.extend({**call, "stage": "reconcile", "batch": number} for call in calls)
        # Accepted decisions are rechecked before entering the snapshot.
        accepted, _ = validated_events(data)
        if cache_path and not cache_path.exists():
            StageCache.write(cache_path, data)
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
        if progress:
            progress(f"Completed reconciliation batch {number}/{len(batches)}")
    # Unresolved collects mentions in groups without an accepted decision.
    unresolved = [
        mention.mention_id
        for group_id, mentions in groups.items()
        if group_id not in resolved
        for mention in mentions
    ]
    return Reconciliation(events=list(resolved.values()), unresolved_mention_ids=unresolved), findings, trace
