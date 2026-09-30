"""Verify the agent protocol and source citation gate without a paid model call."""

import unittest

from bb.agent import EvidenceTools, answer_question
from bb.model_provider import ModelTurn, ToolCall
from bb.models import Anchor, BatchExtraction, Reconciliation, ReviewSnapshot


class FakeCorpus:
    sources = {"SRC-1": object()}

    def search(self, query: str, limit: int = 15):
        return [{"source_id": "SRC-1", "line": 1, "text": "A documented clinical observation."}]

    def validate_anchor(self, anchor: Anchor) -> None:
        if anchor.source_id != "SRC-1" or anchor.lines != [1]:
            raise ValueError("Invalid anchor")


class FakeModel:
    model_name = "offline-fake"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, system, history, tools=None, max_tokens=5000):
        self.calls += 1
        if self.calls == 1:
            return ModelTurn(text="", tool_calls=[ToolCall("call-1", "search", {"query": "observation"})])
        return ModelTurn(text="The record contains a clinical observation [SRC-1:L1].")


class AgentTests(unittest.TestCase):
    def test_agent_selects_tool_and_validates_source_reference(self) -> None:
        snapshot = ReviewSnapshot(
            source_hashes={}, extraction_model="offline-fake",
            extraction=BatchExtraction(), reconciliation=Reconciliation(),
        )
        calculation = {
            "period": {}, "therapy_sessions": {}, "sessions_by_type": {},
            "therapy_days": {}, "therapy_minutes": {}, "weeks": [], "events": [],
            "measure_instances": [], "totals_complete": True,
            "unquantified_event_ids": [], "unresolved_mention_ids": [],
        }
        model = FakeModel()
        result = answer_question("What is documented?", model, EvidenceTools(FakeCorpus(), snapshot, calculation))
        self.assertEqual(model.calls, 2)
        self.assertEqual(result.citations, ["SRC-1:L1"])
        self.assertFalse(result.audit)
        self.assertIn("tool", [item["stage"] for item in result.trace])


if __name__ == "__main__":
    unittest.main()
