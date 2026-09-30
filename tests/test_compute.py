"""Domain-level checks independent of the development questions."""

import unittest

from bb.compute import calculate_review, event_minutes
from bb.models import BatchExtraction, PlanGoal, Reconciliation, ResolvedEvent, TimeSpan


def span(start: str, end: str) -> TimeSpan:
    return TimeSpan(start=start, end=end)


class CalculationTests(unittest.TestCase):
    def test_interval_union_exclusion_and_conflict(self) -> None:
        event = ResolvedEvent(
            event_id="case:visit",
            service_date="2026-03-02",
            service_type="group psychotherapy",
            disposition="delivered",
            patient_therapy="yes",
            interval_options=[
                [span("09:00", "10:00"), span("09:45", "10:15")],
                [span("09:10", "10:15")],
            ],
            excluded_intervals=[span("09:30", "09:45")],
        )
        self.assertEqual([sum(option.values()) for option in event_minutes(event)], [60, 50])

    def test_week_goal_remains_indeterminate_across_bounds(self) -> None:
        first = ResolvedEvent(
            event_id="case:one",
            service_date="2026-03-02",
            service_type="individual therapy",
            disposition="delivered",
            patient_therapy="yes",
            interval_options=[[span("09:00", "10:00")]],
        )
        second = ResolvedEvent(
            event_id="case:two",
            service_date="2026-03-04",
            service_type="family psychotherapy",
            disposition="uncertain",
            patient_therapy="uncertain",
            interval_options=[[span("09:00", "10:00")]],
        )
        goal = PlanGoal(source_id="PLAN", lines=[1], minimum_days=2, minimum_minutes=100)
        result = calculate_review(
            Reconciliation(events=[first, second]),
            BatchExtraction(goals=[goal]),
            "2026-03-02",
            "2026-03-08",
        )
        self.assertEqual(result["therapy_days"], {"minimum": 1, "maximum": 2})
        self.assertEqual(result["therapy_minutes"], {"minimum": 60, "maximum": 120})
        self.assertEqual(result["weeks"][0]["goals"][0]["status"], "indeterminate")


if __name__ == "__main__":
    unittest.main()
