# Question

How should the two January 21 video connection records be represented as treatment encounters and patient psychotherapy time? Explain the disconnected interval.

# Answer

Represent the two video connections as **one delivered individual psychotherapy encounter**, not two sessions. Both call IDs belong to appointment HG-A112, and the signed note says the reconnection continued the same clinical encounter [BH-D106:L3,L7,L13,L17,L18,L19].

Count **45 minutes of patient psychotherapy time**: 13:00–13:20 (20 minutes) plus 13:30–13:55 (25 minutes). Exclude 13:20–13:30: the connection was lost and there was **no therapeutic contact** during those 10 minutes. Thus the 55-minute elapsed span is not 55 minutes of treatment [BH-D106:L7,L17,L18].

# Evidence

Original document lines referenced in the answer:

## BH-D106 — [BH-D106_telehealth_2026-01-21.txt](<../data/BH-D106_telehealth_2026-01-21.txt>)

```text
L0003 Individual psychotherapy | Encounter HG-E112 | Appointment HG-A112
L0007 Patient contact occurred 13:00–13:20 and 13:30–13:55. Connection was lost from 13:20–13:30; there was no therapeutic contact during that interval. Total patient psychotherapy contact: 45 minutes. The reconnection continued the same clinical encounter under original appointment HG-A112.
L0013 Electronically signed: Mira Patel, LCSW | January 21, 2026, 15:04
L0017 HG-A112 | VC-112A | January 21 13:00 | January 21 13:20
L0018 HG-A112 | VC-112B | January 21 13:30 | January 21 13:55
L0019 Second call reason: Rejoin original appointment after network disconnect.
```

# Run information

- Online model calls: 3
