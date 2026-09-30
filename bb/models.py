"""Versioned contracts shared by extraction, reconciliation, and review."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TimeSpan(BaseModel):
    start: str = Field(description="Local HH:MM start time")
    end: str = Field(description="Local HH:MM end time")

    @field_validator("start", "end")
    @classmethod
    def valid_clock(cls, value: str) -> str:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Time must use 24-hour HH:MM")
        return value


def _valid_date(value: str | None) -> str | None:
    if value is not None:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Date must use YYYY-MM-DD")
        date.fromisoformat(value)
    return value


def _empty_string(value: str | None) -> str:
    return "" if value is None else value


def _empty_list(value: list | None) -> list:
    return [] if value is None else value


class Anchor(BaseModel):
    source_id: str
    lines: list[int] = Field(min_length=1, max_length=12)

    @field_validator("lines")
    @classmethod
    def positive_lines(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError("Source line numbers must be positive")
        return sorted(set(values))

    def reference(self) -> str:
        numbers = ",".join(f"L{line}" for line in self.lines)
        return f"{self.source_id}:{numbers}"


class EventMention(BaseModel):
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

    @field_validator("note", mode="before")
    @classmethod
    def optional_note(cls, value: str | None) -> str:
        return _empty_string(value)

    @field_validator("actual_intervals", "scheduled_intervals", "nontherapy_intervals", mode="before")
    @classmethod
    def optional_intervals(cls, value: list | None) -> list:
        return _empty_list(value)

    @field_validator("service_date")
    @classmethod
    def valid_service_date(cls, value: str | None) -> str | None:
        return _valid_date(value)

    def finalize_id(self) -> None:
        key = f"{self.source_id}|{self.patient_id}|{self.encounter_id}|{self.service_date}|{self.lines}"
        self.mention_id = sha256(key.encode()).hexdigest()[:16]

    def anchor(self) -> Anchor:
        return Anchor(source_id=self.source_id, lines=self.lines)


class PlanGoal(BaseModel):
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

    @field_validator("period", mode="before")
    @classmethod
    def normalize_period(cls, value: str | None) -> str | None:
        if value is None:
            return None
        lowered = value.lower().strip()
        if lowered == "week_monday_sunday" or ("monday" in lowered and "sunday" in lowered):
            return "week_monday_sunday"
        if lowered in {"weekly", "week", "each week"}:
            return "weekly_unspecified_boundary"
        return value

    @field_validator("included_services", "excluded_services", mode="before")
    @classmethod
    def optional_services(cls, value: list | None) -> list:
        return _empty_list(value)

    @field_validator("description", mode="before")
    @classmethod
    def optional_description(cls, value: str | None) -> str:
        return _empty_string(value)

    @field_validator("effective_from", "effective_to")
    @classmethod
    def valid_effective_date(cls, value: str | None) -> str | None:
        return _valid_date(value)

    def anchor(self) -> Anchor:
        return Anchor(source_id=self.source_id, lines=self.lines)


class MeasureMention(BaseModel):
    source_id: str
    lines: list[int] = Field(min_length=1, max_length=12)
    instrument: str
    form_id: str | None = None
    completed_date: str | None = None
    score: float | None = None
    copied_from_form: str | None = None
    note: str = ""

    @field_validator("note", mode="before")
    @classmethod
    def optional_note(cls, value: str | None) -> str:
        return _empty_string(value)

    @field_validator("completed_date")
    @classmethod
    def valid_completed_date(cls, value: str | None) -> str | None:
        return _valid_date(value)

    def anchor(self) -> Anchor:
        return Anchor(source_id=self.source_id, lines=self.lines)


class Observation(BaseModel):
    source_id: str
    lines: list[int] = Field(min_length=1, max_length=12)
    date: str | None = None
    subject: str = "patient"
    theme: str
    statement: str
    polarity: Literal["positive", "negative", "uncertain", "planned"] = "positive"

    @field_validator("date")
    @classmethod
    def valid_observation_date(cls, value: str | None) -> str | None:
        return _valid_date(value)

    def anchor(self) -> Anchor:
        return Anchor(source_id=self.source_id, lines=self.lines)


class BatchExtraction(BaseModel):
    events: list[EventMention] = Field(default_factory=list)
    goals: list[PlanGoal] = Field(default_factory=list)
    measures: list[MeasureMention] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)


class ResolvedEvent(BaseModel):
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
        return _valid_date(value)


class Reconciliation(BaseModel):
    events: list[ResolvedEvent] = Field(default_factory=list)
    unresolved_mention_ids: list[str] = Field(default_factory=list)


class AuditFinding(BaseModel):
    code: str
    detail: str
    source_refs: list[str] = Field(default_factory=list)


class ReviewSnapshot(BaseModel):
    source_hashes: dict[str, str]
    extraction_model: str
    extraction: BatchExtraction
    reconciliation: Reconciliation
    findings: list[AuditFinding] = Field(default_factory=list)
