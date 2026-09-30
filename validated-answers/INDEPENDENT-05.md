# Question

The January 19 group roster, its next-day correction, and a copy received on January 26 show different departure information. Which patient interval should be used for the January 19 group, what are its therapy minutes, and does the received copy create or restore any contact?

# Answer

Use **10:00–11:15** as the patient’s corrected attendance interval for the January 19 group. The original roster lists an 11:30 departure, but the signed January 20 correction replaces that field with 11:15 and leaves the 10:00 arrival unchanged. [BH-D102:L8,L9] [BH-D103:L7,L9,L15,L16]

Exclude the documented nontherapeutic break from 10:45–11:00. That leaves **10:00–10:45 (45 minutes) plus 11:00–11:15 (15 minutes) = 60 therapy minutes**. [BH-D101:L6,L8] The copy received January 26 retransmits the original roster *without* the correction sheet; its 11:30 entry does not restore the later departure or create another contact. The receipt date is an inbox-processing date, and the copy records no additional visit. [BH-D104:L4,L8,L14,L20]

# Evidence

Original document lines referenced in the answer:

## BH-D101 — [BH-D101_group_content_2026-01-19.txt](<../data/BH-D101_group_content_2026-01-19.txt>)

```text
L0006 Scheduled group: 10:00–11:30. Nontherapeutic break: 10:45–11:00.
L0008 Today's group addressed recognizing the sequence between a triggering situation, an anxious prediction, physical activation, and an avoidance response. The facilitator used a worked example involving an unanswered work email. Members then practiced describing the prediction without treating it as an established outcome, and selected a small approach behavior they could attempt during the week. The break was for restroom use and refreshments; there was no facilitated discussion, assigned therapeutic activity, or patient treatment during that interval.
```

## BH-D102 — [BH-D102_original_attendance_2026-01-19.txt](<../data/BH-D102_original_attendance_2026-01-19.txt>)

```text
L0008 Scheduled opening: 10:00 | Scheduled closing: 11:30
L0009 Patient arrival: 10:00 | Patient departure: 11:30 | Status: Attended
```

## BH-D103 — [BH-D103_attendance_correction_2026-01-20.txt](<../data/BH-D103_attendance_correction_2026-01-20.txt>)

```text
L0007 Correction: Patient departure for HG-E110 is 11:15, replacing the original roster value of 11:30. Patient arrival remains 10:00.
L0009 During review of the same-day transfer, the original group roster was found to retain the scheduled group closing time in Rowan's departure field. The room-transfer record shows Rowan leaving skills room B at 11:15 and being received by the individual clinician at 11:15. I reviewed that record with the receiving clinician and confirm the corrected departure time above. The group continued for other members until its scheduled close.
L0015 Electronically signed: Leah Chen, LCSW | January 20, 2026, 08:42
L0016 Correction status: Final
```

## BH-D104 — [BH-D104_resent_roster_received_2026-01-26.txt](<../data/BH-D104_resent_roster_received_2026-01-26.txt>)

```text
L0004 Received: January 26, 2026, 16:22 | Sender: Outpatient group records queue
L0008 The attached attendance sheet was resent following a request for the original group roster. The transmitted packet contains the cover sheet and the original patient-specific roster extract. No correction sheet was included in this transmission. Intake staff indexed the received copy under the service date printed on the roster. The receipt date is the inbox processing date.
L0014 Patient arrival: 10:00 | Patient departure: 11:30 | Status: Attended
L0020 Records intake: indexed by Ana Reed, records assistant, January 26, 2026, 16:31. This is a retransmission of the January 19 roster for HG-E110. The received copy contains no new clinician signature and records no additional visit.
```

# Run information

- Online model calls: 3
