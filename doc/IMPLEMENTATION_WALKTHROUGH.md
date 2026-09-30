# Implementation walkthrough and discussion guide

This is a guide for walking through the submitted system, explaining its decisions, and trying related questions with a reviewer. For exact commands, use the [runbook](RUNBOOK.md). For the evaluated files, use the [submission guide](SUBMISSION.md).

## A 30-minute walkthrough

| Time | What to show | Reviewer question it answers |
| --- | --- | --- |
| 0–3 min | State the problem and open a [development report](../validated-answers/DEV-01.md). | What is the end-to-end deliverable? |
| 3–8 min | Open [`abstraction.json`](../artifacts/reviewed-development/abstraction.json): source hashes, extracted mentions, reconciled encounters and audit findings. | What does the clinical abstraction represent? |
| 8–13 min | Trace the January 19 corrected group attendance through source lines, event linkage and [`calculation.json`](../artifacts/reviewed-development/calculation.json). | Why is one encounter counted once and why are the minutes defensible? |
| 13–18 min | Open [`DEV-02`](../validated-answers/DEV-02.md) and [`DEV-03`](../validated-answers/DEV-03.md). | How do interval arithmetic and uncertainty affect weekly goals? |
| 18–23 min | Ask a related unseen question in Gradio or the CLI; inspect its tool trace. | How does the system handle a question it was not scripted to answer? |
| 23–27 min | Show snapshot hash checks, unit tests, and the separate offline/online run records. | What can be reproduced or audited? |
| 27–30 min | Discuss input scope and a bounded next experiment. | What would you investigate next? |

## Trace one conclusion back to its sources

The January 19 group record illustrates why a search-and-summarize answer would be fragile. An original attendance record said the patient left at 11:30. A later correction set departure to 11:15; a copy received January 26 retransmitted the earlier record rather than documenting a new encounter. [`BH-D103`](../data/BH-D103_attendance_correction_2026-01-20.txt) and [`BH-D104`](../data/BH-D104_resent_roster_received_2026-01-26.txt) identify those distinctions. The separate individual session began at 11:15 in [`BH-D105`](../data/BH-D105_individual_2026-01-19.txt). The reconciled review counts **two therapy contacts on one day**, and the deterministic calculation gives **90 patient therapy minutes** for January 19. The [DEV-04 report](../validated-answers/DEV-04.md) shows the exact included lines and the separate January 21 reconstruction.

Another useful trace is the January 26 individual encounter. Two clinician records support one encounter but disagree on its duration. The calculator retains a **40–50 minute range**; it does not pick an arbitrary number. That range makes the final week's minute threshold indeterminate, even though the day count is known. See [INDEPENDENT-03](../validated-answers/INDEPENDENT-03.md) and [INDEPENDENT-16](../validated-answers/INDEPENDENT-16.md).

## Why these components exist

| Decision | Reason | Where to inspect |
| --- | --- | --- |
| Keep original text with source IDs, hashes and line anchors | A reviewer can verify every claim and detect a changed corpus. | [`source.py`](../bb/source.py), `source_hashes` in the abstraction. |
| Use lexical search plus complete inventories | Search finds candidates; a paginated inventory can support counts and absence claims without mistaking top hits for all records. | [`source.py`](../bb/source.py), `search` and `scan` in [`agent.py`](../bb/agent.py). |
| Extract claims before reconciling events | The same event can appear in attendance, clinical, administrative and corrected records. The source claim must survive even when the final event decision differs. | [`extract.py`](../bb/extract.py), [`reconcile.py`](../bb/reconcile.py). |
| Validate and repair model output at stage boundaries | An invalid source anchor or incomplete extraction should be returned for bounded correction before it contaminates a reusable snapshot. | [`repair.py`](../bb/repair.py), [`models.py`](../bb/models.py). |
| Calculate minutes and goals in code | Interval union, breaks, ranges and weekly aggregation are auditable and deterministic. | [`compute.py`](../bb/compute.py), `calculation.json`. |
| Give the online agent five focused tools | A new question may need a direct source quote, related competing records, an exhaustive inventory or a calculation. A bounded tool loop makes those choices visible. | [`agent.py`](../bb/agent.py), `trace.jsonl`. |
| Separate offline preparation from online answers | A validated abstraction can serve many questions while each answer remains independently traceable. | [`cli.py`](../bb/cli.py), [`web.py`](../bb/web.py), `run.json`. |
| Use one `ModelPort` with SDK adapters | Provider-specific wire formats stay outside the abstraction, calculation and agent logic. | [`model_provider.py`](../bb/model_provider.py). |

The result is a small agent system, not a fixed workflow of five question templates. The offline processing stages are ordered because they build a reusable evidence model; the online agent chooses tools according to the new question. This is a prototype for one text corpus at a time. Larger or mixed-format deployments would need ingestion and operational changes, while the source-anchor and event contracts remain useful boundaries.

## Related questions to explore live

These examples probe different reasoning paths rather than repeating the supplied five:

1. **Evidence status:** “Does the group authorization prove attendance at eight sessions?” Expected method: compare the authorization with attendance records; distinguish allowed visits from delivered care. See [INDEPENDENT-01](../validated-answers/INDEPENDENT-01.md).
2. **Event identity:** “Do the January 9 clinician notes represent two family visits?” Expected method: inspect their shared encounter ID and patient-presence evidence. See [INDEPENDENT-02](../validated-answers/INDEPENDENT-02.md).
3. **Corrections and copies:** “Does the January 26 received roster create another January 19 group visit?” Expected method: follow original, correction and retransmission roles. See [INDEPENDENT-17](../validated-answers/INDEPENDENT-17.md).
4. **Time scope:** “Should medication-management minutes satisfy a psychotherapy goal?” Expected method: inspect service type and calculation inclusion rules. See [INDEPENDENT-18](../validated-answers/INDEPENDENT-18.md).
5. **Causal restraint:** “Did therapy cause the PHQ-9 score decrease?” Expected method: distinguish observed scores and dates from unsupported causation. See [INDEPENDENT-19](../validated-answers/INDEPENDENT-19.md).

For a genuinely new question, write it to a new questions JSON file or ask it in Gradio. Inspect the answer, its citations, and its trace before judging it. If the answer is wrong, classify the failure by source intake, retrieval, extraction, event linkage, calculation or final synthesis. Improve the responsible system boundary rather than adding a rule for that one question.

## A bounded half-day working session

The final stage described in the exercise is collaborative work on a bounded problem. A productive demonstration would use one new document or one related question chosen by the team:

1. Agree on the observable expected behavior and the source evidence needed to establish it.
2. Run the existing system on the new case; save the run directory and inspect the trace.
3. Locate the failing boundary, if any: parser/source addressing, extraction, reconciliation, arithmetic, retrieval or answer synthesis.
4. Make one generalizable change, add a focused regression check if it protects a real boundary, and rerun that case plus the five development questions.
5. Explain the result, remaining uncertainty, model usage and evidence trail.

This exercise tests whether the abstraction and tools are understandable and extensible, not whether a prompt can be tuned to memorize a particular answer.
