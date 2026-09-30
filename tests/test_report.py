"""Keep the downloadable report grounded and its call count online-only."""

import unittest

from bb.models import Anchor
from bb.report import model_call_count, render_answer_markdown
from bb.source import Source


class SourceStub:
    def __init__(self):
        self.source = Source(
            source_id="SRC-1", filename="note.txt", absolute_path="/example/note.txt",
            sha256="hash", lines=("first line", "source evidence", "third line"),
        )

    def get(self, source_id):
        if source_id != "SRC-1":
            raise KeyError(source_id)
        return self.source

    def validate_anchor(self, anchor: Anchor):
        if anchor.source_id != "SRC-1" or any(line > 3 for line in anchor.lines):
            raise ValueError("Invalid source anchor")


class ReportTests(unittest.TestCase):
    def test_report_contains_source_evidence_without_model_label(self):
        trace = [
            {"stage": "answer", "usage": {"input_tokens": 5, "output_tokens": 2}},
            {"stage": "tool", "name": "open_source"},
            {"stage": "answer", "usage": {"input_tokens": 6, "output_tokens": 3}},
        ]
        calls = model_call_count(trace)
        report = render_answer_markdown(
            "What happened?", "The source confirms it [SRC-1:L2].",
            ["SRC-1:L2"], SourceStub(), calls,
        )
        self.assertEqual(calls, 2)
        self.assertIn("# Question\n\nWhat happened?", report)
        self.assertIn("# Answer\n\nThe source confirms it", report)
        self.assertIn("L0002 source evidence", report)
        self.assertIn("- Online model calls: 2", report)
        self.assertNotIn("**Model:**", report)
        self.assertNotIn("- Model calls:", report)


if __name__ == "__main__":
    unittest.main()
