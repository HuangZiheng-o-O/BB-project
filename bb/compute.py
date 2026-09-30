"""Deterministic arithmetic over reconciled, source-linked encounter decisions."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
import re
from typing import Any

from bb.models import AuditFinding, BatchExtraction, Reconciliation, ResolvedEvent, TimeSpan


def _instant(day: date, clock: str) -> datetime:
    """Combine a local service date and validated 24-hour clock value."""
    return datetime.combine(day, time.fromisoformat(clock))


def _ranges(day: date, spans: list[TimeSpan]) -> list[tuple[datetime, datetime]]:
    """Convert clock spans to datetimes, carrying overnight ends forward."""
    # Each pair is an absolute contact interval anchored to the service date.
    ranges = []
    # Span is the next clock-only interval from the event decision.
    for span in spans:
        # Clock-only spans need the encounter date before duration is meaningful.
        start, end = _instant(day, span.start), _instant(day, span.end)
        if end <= start:
            end += timedelta(days=1)
        ranges.append((start, end))
    return ranges


def _union(ranges: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Merge overlapping or touching intervals to prevent double counting."""
    # The accumulator holds disjoint intervals in chronological order.
    merged: list[tuple[datetime, datetime]] = []
    # Start and end identify the next sorted interval to merge.
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = merged[-1][0], max(merged[-1][1], end)
        else:
            merged.append((start, end))
    return merged


def _subtract(
    included: list[tuple[datetime, datetime]], excluded: list[tuple[datetime, datetime]]
) -> list[tuple[datetime, datetime]]:
    """Remove breaks and other excluded intervals from candidate contact."""
    # Normalize included spans before cutting so overlaps count only once.
    pieces = _union(included)
    # Cut boundaries are the next excluded, already-merged interval.
    for cut_start, cut_end in _union(excluded):
        # Rebuild the surviving pieces after each excluded span.
        next_pieces = []
        # Start and end identify one currently surviving contact piece.
        for start, end in pieces:
            if cut_end <= start or cut_start >= end:
                next_pieces.append((start, end))
            else:
                if start < cut_start:
                    next_pieces.append((start, cut_start))
                if cut_end < end:
                    next_pieces.append((cut_end, end))
        pieces = next_pieces
    return pieces


def _minute_map(ranges: list[tuple[datetime, datetime]]) -> dict[str, int]:
    """Assign each contact minute to its actual calendar date."""
    # Keys are calendar dates, including the next day for overnight contact.
    minutes: dict[str, int] = defaultdict(int)
    # Start and end bound one deduplicated contact interval.
    for start, end in ranges:
        # Move the cursor to midnight whenever an interval crosses a date boundary.
        cursor = start
        while cursor < end:
            # Tomorrow bounds the current calendar-day slice.
            tomorrow = datetime.combine(cursor.date() + timedelta(days=1), time.min)
            # Stop at the earlier of midnight and the actual interval end.
            stop = min(end, tomorrow)
            minutes[cursor.date().isoformat()] += int((stop - cursor).total_seconds() // 60)
            cursor = stop
    return dict(minutes)


def event_minutes(event: ResolvedEvent) -> list[dict[str, int]]:
    """Return all plausible patient-minute maps for one event, including zero if uncertain."""
    if event.disposition == "not_delivered" or event.patient_therapy == "no":
        return [{}]
    # An event without a dated patient interval cannot contribute known minutes.
    if not event.service_date or not event.interval_options:
        return [{}]
    # Convert clock spans using the event date, then subtract nontherapy time.
    day = date.fromisoformat(event.service_date)
    # Excluded holds breaks and other nontherapy spans in absolute time.
    excluded = _ranges(day, event.excluded_intervals)
    # Each choice represents one supported version of patient contact.
    choices = [
        _minute_map(_subtract(_ranges(day, option), excluded))
        for option in event.interval_options
    ]
    if event.disposition == "uncertain" or event.patient_therapy == "uncertain":
        choices.append({})
    return choices


def _therapy_type(service_type: str) -> str | None:
    """Classify eligible therapy without counting administrative services."""
    # Word boundaries avoid accidental matches inside unrelated service names.
    words = set(re.findall(r"[a-z]+", service_type.lower()))
    if words & {"medication", "management", "coordination", "collateral", "administrative", "outreach"}:
        return None
    # Category is the first recognized therapy setting in the service label.
    for category in ("individual", "group", "family"):
        if category in words:
            return category
    return "therapy_unspecified" if words & {"psychotherapy", "therapy"} else None


def _bounds(values: list[int]) -> dict[str, int]:
    """Retain the minimum and maximum across supported event scenarios."""
    return {"minimum": min(values, default=0), "maximum": max(values, default=0)}


def _week_start(day: date) -> date:
    """Find the Monday that starts the day’s reporting week."""
    return day - timedelta(days=day.weekday())


def _measure_instances(extraction: BatchExtraction) -> list[dict[str, Any]]:
    """Group imported copies with their original completed questionnaire."""
    # Instrument and form identity together define one completed instance.
    grouped: dict[tuple[str, str], list] = defaultdict(list)
    # Item is one extracted claim about a questionnaire or copy.
    for item in extraction.measures:
        # A copy points back to its original form instead of becoming a new test.
        identity = item.copied_from_form or item.form_id or item.anchor().reference()
        grouped[(item.instrument.strip().lower(), identity)].append(item)
    # Keep conflicting dates or scores visible for review.
    instances = []
    # Instrument and identity name the form; claims are its source mentions.
    for (instrument, identity), claims in sorted(grouped.items()):
        # Distinct values expose disagreement among claims about the same form.
        dates = sorted({item.completed_date for item in claims if item.completed_date})
        scores = sorted({item.score for item in claims if item.score is not None})
        instances.append(
            {
                "instrument": instrument,
                "identity": identity,
                "completed_dates": dates,
                "scores": scores,
                "conflicting_values": len(dates) > 1 or len(scores) > 1,
                "source_refs": [item.anchor().reference() for item in claims],
                "copy_refs": [item.anchor().reference() for item in claims if item.copied_from_form],
            }
        )
    return instances


def calculate_review(
    reconciliation: Reconciliation,
    extraction: BatchExtraction,
    period_start: str | None = None,
    period_end: str | None = None,
    findings: list[AuditFinding] | None = None,
) -> dict[str, Any]:
    """Build a complete event ledger and bounded totals without asking the model to add."""
    # These inclusive dates restrict totals without changing the source ledger.
    first = date.fromisoformat(period_start) if period_start else None
    # Last is the inclusive end of the requested reporting window.
    last = date.fromisoformat(period_end) if period_end else None
    # Mention lookup lets every calculated event retain its original citations.
    mentions = {mention.mention_id: mention for mention in extraction.events}
    # The ledger includes eligible and ineligible encounters for auditability.
    ledger: list[dict[str, Any]] = []
    # Per-day bounds aggregate all supported alternatives across events.
    day_min: dict[str, int] = defaultdict(int)
    # Day max tracks the largest supported minutes on each date.
    day_max: dict[str, int] = defaultdict(int)
    # Certain and possible day sets produce lower and upper day counts.
    day_certain: set[str] = set()
    # Day possible includes dates present in at least one event option.
    day_possible: set[str] = set()
    # Each service category stores certain and possible session counts.
    type_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    # Missing intervals make otherwise eligible event totals incomplete.
    unquantified_event_ids: list[str] = []
    # Coverage and time-scope findings qualify the reported numeric bounds.
    coverage_gaps = [
        finding.detail for finding in (findings or [])
        if finding.code in {"possible_event_omission", "time_scope_uncertain"}
    ]

    # Event is the next reconciled encounter, including nontherapy events.
    for event in reconciliation.events:
        # Preserve each decision and its source references in the event ledger.
        source_refs = sorted(
            {mentions[item].anchor().reference() for item in event.supporting_mentions + event.opposing_mentions if item in mentions}
        )
        # Options retain conflicting patient-time interpretations separately.
        options = event_minutes(event)
        # Calendar dates may include the day after an overnight encounter.
        date_totals = sorted(set(day for option in options for day in option))
        # Event totals summarize each option before category aggregation.
        event_totals = [sum(option.values()) for option in options]
        # Service category determines whether this event can count as therapy.
        category = _therapy_type(event.service_type)
        # Eligible marks categories included in therapy aggregates.
        eligible = category is not None
        # Undated events remain visible and can make completeness uncertain.
        within = not event.service_date or (
            (first is None or date.fromisoformat(event.service_date) >= first)
            and (last is None or date.fromisoformat(event.service_date) <= last)
        )
        if eligible and within:
            if event.disposition != "not_delivered" and event.patient_therapy != "no" and (not event.service_date or not event.interval_options):
                unquantified_event_ids.append(event.event_id)
            # Value is the minute total for one supported event scenario.
            type_counts[category][0] += int(all(value > 0 for value in event_totals))
            type_counts[category][1] += int(any(value > 0 for value in event_totals))
            for day in date_totals:
                if first and date.fromisoformat(day) < first or last and date.fromisoformat(day) > last:
                    continue
                # Compare all supported options for this calendar date.
                possible = [option.get(day, 0) for option in options]
                day_min[day] += min(possible)
                day_max[day] += max(possible)
                if min(possible) > 0:
                    day_certain.add(day)
                if max(possible) > 0:
                    day_possible.add(day)
        ledger.append(
            {
                "event_id": event.event_id,
                "service_date": event.service_date,
                "service_type": event.service_type,
                "service_category": category,
                "disposition": event.disposition,
                "patient_therapy": event.patient_therapy,
                "eligible_service": eligible,
                "within_period": within,
                "unquantified": event.event_id in unquantified_event_ids,
                "minute_options": options,
                "minutes": _bounds(event_totals),
                "source_refs": source_refs,
                "supporting_mentions": event.supporting_mentions,
                "opposing_mentions": event.opposing_mentions,
                "decision_notes": event.decision_notes,
            }
        )

    # Group possible dates by the Monday that starts their reporting week.
    week_days: dict[str, list[str]] = defaultdict(list)
    for day in sorted(day_possible):
        week_days[_week_start(date.fromisoformat(day)).isoformat()].append(day)
    # Every week in the requested period gets an explicit output row.
    weeks: list[dict[str, Any]] = []
    # Include zero-contact weeks when the requested period spans them.
    if first and last:
        # Cursor walks Monday week starts through the inclusive period end.
        cursor = _week_start(first)
        while cursor <= last:
            week_days.setdefault(cursor.isoformat(), [])
            cursor += timedelta(days=7)
    # Week is a Monday key; days are possible-contact dates within it.
    for week, days in sorted(week_days.items()):
        # The Monday determines the inclusive Sunday ending this week.
        monday = date.fromisoformat(week)
        weeks.append(
            {
                "week_start": week,
                "week_end": (monday + timedelta(days=6)).isoformat(),
                "days": {day: _bounds([day_min[day], day_max[day]]) for day in days},
                "therapy_days": {
                    "minimum": sum(day in day_certain for day in days),
                    "maximum": len(days),
                },
                "minutes": {
                    "minimum": sum(day_min[day] for day in days),
                    "maximum": sum(day_max[day] for day in days),
                },
            }
        )
    # Raw plan goals remain available alongside evaluated weekly statuses.
    goals = [goal.model_dump() for goal in extraction.goals]
    for week in weeks:
        # A goal is certain only when the lower bound meets both thresholds.
        # A plan applies only while effective and with an explicit week boundary.
        applicable = [
            goal for goal in extraction.goals
            if goal.period == "week_monday_sunday"
            and (not goal.effective_from or goal.effective_from <= week["week_end"])
            and (not goal.effective_to or goal.effective_to >= week["week_start"])
            and goal.minimum_days is not None and goal.minimum_minutes is not None
        ]
        week["goals"] = []
        for goal in applicable:
            # Compare both bounds against both plan requirements.
            day_bounds, minute_bounds = week["therapy_days"], week["minutes"]
            if day_bounds["minimum"] >= goal.minimum_days and minute_bounds["minimum"] >= goal.minimum_minutes:
                status = "met"
            elif day_bounds["maximum"] < goal.minimum_days or minute_bounds["maximum"] < goal.minimum_minutes:
                status = "unmet"
            else:
                status = "indeterminate"
            week["goals"].append(
                {
                    "source_ref": goal.anchor().reference(),
                    "minimum_days": goal.minimum_days,
                    "minimum_minutes": goal.minimum_minutes,
                    "status": status,
                }
            )
    return {
        "period": {"start": period_start, "end": period_end},
        "events": ledger,
        # Key names a therapy category; values are its count bounds.
        "sessions_by_type": {key: _bounds(values) for key, values in sorted(type_counts.items())},
        # Values are the certain and possible counts for each service type.
        "therapy_sessions": {
            "minimum": sum(values[0] for values in type_counts.values()),
            "maximum": sum(values[1] for values in type_counts.values()),
        },
        "therapy_days": {"minimum": len(day_certain), "maximum": len(day_possible)},
        "therapy_minutes": {"minimum": sum(day_min.values()), "maximum": sum(day_max.values())},
        "unquantified_event_ids": unquantified_event_ids,
        "unresolved_mention_ids": reconciliation.unresolved_mention_ids,
        "coverage_gaps": coverage_gaps,
        "totals_complete": not unquantified_event_ids and not reconciliation.unresolved_mention_ids and not coverage_gaps,
        "weeks": weeks,
        "goals": goals,
        "measure_instances": _measure_instances(extraction),
    }
