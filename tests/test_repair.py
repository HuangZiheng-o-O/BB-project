"""Verify generic model repair and source-anchor normalization."""

import json
import unittest

from bb.extract import _payload_errors
from bb.model_provider import ModelTurn
from bb.models import Anchor, AuditFinding, BatchExtraction, EventMention, Reconciliation, ReviewSnapshot, validate_snapshot_reuse
from bb.repair import StageValidationError, generate_checked_json


class SequenceModel:
    """Return predetermined JSON candidates across repair attempts."""

    model_name = "sequence-model"

    def __init__(self, outputs):
        """Save candidate outputs and the prompts used for each attempt."""
        self.outputs = outputs
        self.prompts = []

    def generate(self, system, history, tools=None, max_tokens=5000, json_mode=False):
        """Advance through candidates without a provider request."""
        self.prompts.append(history[0]["content"])
        return ModelTurn(text=json.dumps(self.outputs[min(len(self.prompts) - 1, len(self.outputs) - 1)]))


class SourceStub:
    """Validate source anchors against a small synthetic document."""

    def validate_anchor(self, anchor):
        """Reject unknown sources and lines outside the synthetic document."""
        if anchor.source_id != "SRC-1" or any(line > 20 for line in anchor.lines):
            raise ValueError("Unknown source line")


class RepairTests(unittest.TestCase):
    """Check generic repair and safe snapshot reuse boundaries."""

    def test_line_labels_become_canonical_integer_anchors(self):
        """Normalize labeled line ranges before formatting citations."""
        mention = EventMention.model_validate({
            "source_id": "SRC-1", "lines": ["L0003-L0006", "L0009"],
            "document_role": "clinical", "status": "delivered",
        })
        self.assertEqual(mention.lines, [3, 4, 5, 6, 9])
        self.assertEqual(mention.anchor().reference(), "SRC-1:L3,L4,L5,L6,L9")
        with self.assertRaises(ValueError):
            Anchor(source_id="SRC-1", lines=["L3-L50"])

    def test_extraction_validation_accepts_normalized_source_evidence(self):
        """Accept source-backed claims after line normalization."""
        payload = {
            "events": [{"source_id": "SRC-1", "lines": ["L0003-L0006"],
                        "document_role": "clinical", "status": "delivered"}],
            "goals": [], "measures": [], "observations": [],
        }
        self.assertEqual(_payload_errors(payload, SourceStub(), {"SRC-1"}), [])

    def test_validation_failure_goes_back_to_model(self):
        """Feed validator errors into a fresh model attempt."""
        model = SequenceModel([{"events": []}, {"events": ["corrected"]}])
        result, trace = generate_checked_json(
            model, "Extract", "Original source",
            lambda value: [] if value.get("events") == ["corrected"] else ["Missing event"],
            max_tokens=100, attempts=2,
        )
        self.assertEqual(result["events"], ["corrected"])
        self.assertIn("Missing event", model.prompts[1])
        self.assertEqual([item["errors"] for item in trace if item["stage"] == "validation"],
                         [["Missing event"], []])

    def test_unrepaired_output_never_reaches_next_stage(self):
        """Stop the pipeline when all bounded repair attempts fail."""
        model = SequenceModel([{"events": []}])
        with self.assertRaises(StageValidationError):
            generate_checked_json(
                model, "Extract", "Original source",
                lambda value: ["Missing event"], max_tokens=100, attempts=2,
            )
        self.assertEqual(len(model.prompts), 2)

    def test_old_rejected_snapshot_cannot_be_reused_online(self):
        """Prevent online answers from using rejected offline claims."""
        snapshot = ReviewSnapshot(
            source_hashes={"SRC-1": "hash"}, extraction_model="sequence-model",
            extraction=BatchExtraction(), reconciliation=Reconciliation(),
            findings=[AuditFinding(code="invalid_source_candidate", detail="Discarded source claim")],
        )
        with self.assertRaisesRegex(ValueError, "rejected or omitted"):
            validate_snapshot_reuse(snapshot, "sequence-model", {"SRC-1": "hash"})
        snapshot.findings = []
        validate_snapshot_reuse(snapshot, "sequence-model", {"SRC-1": "hash"})


if __name__ == "__main__":
    unittest.main()
