"""Versioned contracts shared by extraction, reconciliation, and review."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TimeSpan(BaseModel):
    """Local clock interval; an end before its start crosses midnight."""

    start: str = Field(description="Local HH:MM start time")
    end: str = Field(description="Local HH:MM end time")

    @field_validator("start", "end")
    @classmethod
    def valid_clock(cls, value: str) -> str:
        """Reject ambiguous or out-of-range clock values."""
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Time must use 24-hour HH:MM")
        return value


def _valid_date(value: str | None) -> str | None:
    """Validate optional calendar dates without changing their representation."""
    if value is not None:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Date must use YYYY-MM-DD")
        date.fromisoformat(value)
    return value


def _empty_string(value: str | None) -> str:
    """Normalize optional model prose to a non-null string."""
    return "" if value is None else value


def _empty_list(value: list | None) -> list:
    """Normalize omitted model arrays before Pydantic validates their items."""
    return [] if value is None else value


def _source_lines(value: object) -> object:
    """Accept numbered source labels while storing one canonical integer anchor."""
    if not isinstance(value, list):
        return value
    # Numbers accumulates every one-based line represented by the model output.
    numbers: list[int] = []
    for entry in value:
        if isinstance(entry, int) and not isinstance(entry, bool):
            numbers.append(entry)
            continue
        if not isinstance(entry, str):
            raise ValueError("Source lines must be integers or L-prefixed line labels")
        # Part is one comma-separated label within a model-provided entry.
        for part in entry.split(","):
            # Match supports one label or a short inclusive range.
            match = re.fullmatch(r"L?(\d+)(?:[-–]L?(\d+))?", part.strip())
            if not match:
                raise ValueError(f"Invalid source line label: {entry}")
            # First and last bound the expanded, size-limited source range.
            first = int(match.group(1))
            last = int(match.group(2)) if match.group(2) else first
            if last < first or last - first >= 12:
                raise ValueError(f"Invalid or oversized source line range: {entry}")
            numbers.extend(range(first, last + 1))
    return numbers


class Anchor(BaseModel):
    """Small, validated set of one-based lines from one original source."""

    source_id: str
    lines: list[int] = Field(min_length=1, max_length=12)

    @field_validator("lines", mode="before")
    @classmethod
    def parse_lines(cls, value: object) -> object:
        """Accept integer lines and compact line labels from model output."""
        return _source_lines(value)

    @field_validator("lines")
    @classmethod
    def positive_lines(cls, values: list[int]) -> list[int]:
        """Canonicalize lines for stable references and duplicate removal."""
        # Value is each requested one-based line number.
        if any(value < 1 for value in values):
            raise ValueError("Source line numbers must be positive")
        return sorted(set(values))

    def reference(self) -> str:
        """Format a citation understood by the report and agent audit."""
        # Numbers joins each validated line with its citation prefix.
        numbers = ",".join(f"L{line}" for line in self.lines)
        return f"{self.source_id}:{numbers}"


class EventMention(BaseModel):
    """One source's claim about an encounter, before conflict resolution."""

    source_id: str
    lines: list[int] = Field(min_length=1, max_length=12)
    patient_id: str | None = None
    encounter_id: str | None = None
    appointment_id: str | None = None
    service_date: str | None = None
    service_type: str | None = None
    document_role: str = Field(description="clinical, attendance, schedule, correction, charge, draft, or administrative")
    status: str = Field(description="What this source asserts, not the reconciled event status")
    patient_present: bool | None = None
    actual_intervals: list[TimeSpan] = Field(default_factory=list)
    scheduled_intervals: list[TimeSpan] = Field(default_factory=list)
    nontherapy_intervals: list[TimeSpan] = Field(default_factory=list)
    correction_field: str | None = None
    correction_value: str | None = None
    duplicate_of: str | None = None
    note: str = ""
    mention_id: str = ""

    @field_validator("lines", mode="before")
    @classmethod
    def parse_lines(cls, value: object) -> object:
        """Normalize this mention's numbered source labels."""
        return _source_lines(value)

    @field_validator("note", mode="before")
    @classmethod
    def optional_note(cls, value: str | None) -> str:
        """Keep absent explanatory text as an empty string."""
        return _empty_string(value)

    @field_validator("actual_intervals", "scheduled_intervals", "nontherapy_intervals", mode="before")
    @classmethod
    def optional_intervals(cls, value: list | None) -> list:
        """Treat omitted contact intervals as an empty set of claims."""
        return _empty_list(value)

    @field_validator("service_date")
    @classmethod
    def valid_service_date(cls, value: str | None) -> str | None:
        """Validate the claimed encounter date when present."""
        return _valid_date(value)

    def finalize_id(self) -> None:
        """Derive a stable mention ID from its source and encounter identity."""
        # Key combines source provenance, event identity, date, and cited lines.
        key = f"{self.source_id}|{self.patient_id}|{self.encounter_id}|{self.service_date}|{self.lines}"
        self.mention_id = sha256(key.encode()).hexdigest()[:16]

    def anchor(self) -> Anchor:
        """Return the original lines supporting this source claim."""
        return Anchor(source_id=self.source_id, lines=self.lines)


class PlanGoal(BaseModel):
    """A sourced treatment-plan target with optional effective dates."""

    source_id: str
    lines: list[int] = Field(min_length=1, max_length=12)
    effective_from: str | None = None
    effective_to: str | None = None
    period: str | None = None
    minimum_days: int | None = None
    minimum_minutes: int | None = None
    included_services: list[str] = Field(default_factory=list)
    excluded_services: list[str] = Field(default_factory=list)
    description: str = ""

    @field_validator("lines", mode="before")
    @classmethod
    def parse_lines(cls, value: object) -> object:
        """Normalize the plan's numbered source labels."""
        return _source_lines(value)

    @field_validator("period", mode="before")
    @classmethod
    def normalize_period(cls, value: str | None) -> str | None:
        """Distinguish an explicit Monday–Sunday week from vague weekly text."""
        if value is None:
            return None
        # Lowered supports equivalent textual forms of a weekly plan period.
        lowered = value.lower().strip()
        if lowered == "week_monday_sunday" or ("monday" in lowered and "sunday" in lowered):
            return "week_monday_sunday"
        if lowered in {"weekly", "week", "each week"}:
            return "weekly_unspecified_boundary"
        return value

    @field_validator("included_services", "excluded_services", mode="before")
    @classmethod
    def optional_services(cls, value: list | None) -> list:
        """Preserve an omitted service list as an empty list."""
        return _empty_list(value)

    @field_validator("description", mode="before")
    @classmethod
    def optional_description(cls, value: str | None) -> str:
        """Normalize omitted plan description text."""
        return _empty_string(value)

    @field_validator("effective_from", "effective_to")
    @classmethod
    def valid_effective_date(cls, value: str | None) -> str | None:
        """Validate an effective-date boundary when provided."""
        return _valid_date(value)

    def anchor(self) -> Anchor:
        """Return the source lines stating the plan goal."""
        return Anchor(source_id=self.source_id, lines=self.lines)


class MeasureMention(BaseModel):
    """One questionnaire claim, including a possible imported copy."""

    source_id: str
    lines: list[int] = Field(min_length=1, max_length=12)
    instrument: str
    form_id: str | None = None
    completed_date: str | None = None
    score: float | None = None
    copied_from_form: str | None = None
    note: str = ""

    @field_validator("lines", mode="before")
    @classmethod
    def parse_lines(cls, value: object) -> object:
        """Normalize the measure's numbered source labels."""
        return _source_lines(value)

    @field_validator("note", mode="before")
    @classmethod
    def optional_note(cls, value: str | None) -> str:
        """Keep absent measure notes as an empty string."""
        return _empty_string(value)

    @field_validator("completed_date")
    @classmethod
    def valid_completed_date(cls, value: str | None) -> str | None:
        """Validate the stated completion date, not an import date."""
        return _valid_date(value)

    def anchor(self) -> Anchor:
        """Return the source lines identifying this measure claim."""
        return Anchor(source_id=self.source_id, lines=self.lines)


class Observation(BaseModel):
    """A patient-specific clinical claim with provenance and polarity."""

    source_id: str
    lines: list[int] = Field(min_length=1, max_length=12)
    date: str | None = None
    subject: str = "patient"
    theme: str
    statement: str
    polarity: Literal["positive", "negative", "uncertain", "planned"] = "positive"

    @field_validator("lines", mode="before")
    @classmethod
    def parse_lines(cls, value: object) -> object:
        """Normalize the observation's numbered source labels."""
        return _source_lines(value)

    @field_validator("date")
    @classmethod
    def valid_observation_date(cls, value: str | None) -> str | None:
        """Validate the observation date when the source supplies one."""
        return _valid_date(value)

    def anchor(self) -> Anchor:
        """Return the source lines supporting this observation."""
        return Anchor(source_id=self.source_id, lines=self.lines)


class BatchExtraction(BaseModel):
    """All candidate claims extracted from one or more source batches."""

    events: list[EventMention] = Field(default_factory=list)
    goals: list[PlanGoal] = Field(default_factory=list)
    measures: list[MeasureMention] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)


class ResolvedEvent(BaseModel):
    """One encounter decision that retains conflicting interval options."""

    event_id: str
    service_date: str | None = None
    service_type: str
    disposition: Literal["delivered", "not_delivered", "uncertain"]
    patient_therapy: Literal["yes", "no", "uncertain"]
    interval_options: list[list[TimeSpan]] = Field(default_factory=list)
    excluded_intervals: list[TimeSpan] = Field(default_factory=list)
    supporting_mentions: list[str] = Field(default_factory=list)
    opposing_mentions: list[str] = Field(default_factory=list)
    decision_notes: str = ""

    @field_validator("service_date")
    @classmethod
    def valid_service_date(cls, value: str | None) -> str | None:
        """Validate the reconciled encounter date when known."""
        return _valid_date(value)


class Reconciliation(BaseModel):
    """Resolved encounters plus mentions the model could not reconcile."""

    events: list[ResolvedEvent] = Field(default_factory=list)
    unresolved_mention_ids: list[str] = Field(default_factory=list)


class AuditFinding(BaseModel):
    """Machine-readable issue linked to the relevant original evidence."""

    code: str
    detail: str
    source_refs: list[str] = Field(default_factory=list)


class ReviewSnapshot(BaseModel):
    """Reusable offline abstraction bound to model and source fingerprints."""

    source_hashes: dict[str, str]
    extraction_model: str
    extraction: BatchExtraction
    reconciliation: Reconciliation
    findings: list[AuditFinding] = Field(default_factory=list)


INVALID_STAGE_FINDINGS = {
    "invalid_extraction_array",
    "invalid_source_candidate",
    "possible_event_omission",
    "invalid_event_decision",
    "unresolved_event_group",
}


def validate_snapshot_reuse(
    snapshot: ReviewSnapshot, model_name: str, source_hashes: dict[str, str],
) -> None:
    """Keep stale or rejected model-stage output out of new answer runs."""
    if snapshot.extraction_model != model_name:
        raise ValueError("The abstraction was produced by a different model")
    if snapshot.source_hashes != source_hashes:
        raise ValueError("Snapshot source hashes do not match the document directory")
    # Rejected findings mark a preparation result unsafe for later answers.
    rejected = sorted({item.code for item in snapshot.findings if item.code in INVALID_STAGE_FINDINGS})
    if rejected:
        raise ValueError(f"The abstraction contains rejected or omitted source claims: {', '.join(rejected)}")
