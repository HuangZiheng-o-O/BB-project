# Question

For the January 6 and January 22 skills groups, calculate Rowan's patient therapy minutes separately using actual attendance and break times, then give the combined amount.

# Answer

- **January 6:** Rowan attended from 10:15 to 11:15, or 60 minutes. Excluding the 10:45–11:00 break, when no therapy was conducted, leaves **45 patient therapy minutes**: 30 minutes before the break plus 15 after it. [BH-D005:L9,L10][BH-D004:L12]
- **January 22:** Rowan attended from 10:30 to 11:30, or 60 minutes. Excluding the nontherapeutic 10:45–11:00 break leaves **45 patient therapy minutes**: 15 minutes before the break plus 30 after it. [BH-D108:L8,L9,L14][BH-D107:L7,L8,L17]

**Combined: 45 + 45 = 90 patient therapy minutes.**

# Evidence

Original document lines referenced in the answer:

## BH-D004 — [group_facilitator_jan06.txt](<../data/group_facilitator_jan06.txt>)

```text
L0012 The whole group took a break from 10:45 to 11:00. No therapy was conducted during that interval. Following the break, the facilitator resumed with a paired planning exercise and a group discussion of barriers to practice at home. 
```

## BH-D005 — [early_group_attendance_roster.txt](<../data/early_group_attendance_roster.txt>)

```text
L0009 Date       | Encounter | Scheduled slot | Patient arrived | Patient departed | Desk status
L0010 2026-01-06 | HG-E102   | 10:00–11:30    | 10:15           | 11:15            | Attended part
```

## BH-D107 — [BH-D107_group_activity_records_2026-01-22_and_29.txt](<../data/BH-D107_group_activity_records_2026-01-22_and_29.txt>)

```text
L0007 January 22, 2026 | Encounter HG-E113
L0008 Scheduled group 10:00–11:30. Nontherapeutic break 10:45–11:00.
L0017 For both dates, the break was unstructured time without therapeutic activity or facilitator treatment. Patient arrival, departure, and attendance status are entered in the separate attendance register.
```

## BH-D108 — [BH-D108_final_attendance_and_cancellation_register.txt](<../data/BH-D108_final_attendance_and_cancellation_register.txt>)

```text
L0008 Service date | Encounter | Service | Scheduled | Actual arrival | Actual departure | Final disposition
L0009 January 22 | HG-E113 | Skills group | 10:00–11:30 | 10:30 | 11:30 | Attended, late arrival
L0014 January 22 attendance attestation: Rowan arrived at 10:30 and remained until the group closed. Signed: Leah Chen, LCSW, January 22, 12:09.
```

# Run information

- Online model calls: 3
