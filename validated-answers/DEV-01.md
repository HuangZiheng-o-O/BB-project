# Question

For January 5–30, 2026, how many therapy sessions did Rowan attend, by service type and in total, and on how many distinct days? Provide a reviewable abstraction with source support and explain records that could lead to duplicate or ineligible counts.

# Answer

**Rowan attended 12 therapy sessions on 11 distinct days from January 5–30, 2026:** 5 individual, 5 group, and 2 family. The session count exceeds the day count because January 19 included a group session and a separate individual session. [BH-D103:L7,L9,L11] [BH-D105:L3,L5,L6,L9]

| Service type | Count | Included service dates and source support |
|---|---:|---|
| Individual | 5 | Jan 5 [BH-D002:L4,L5,L6,L8]; Jan 14 [BH-D011:L4,L5,L6,L7]; Jan 19 [BH-D105:L3,L5,L6,L9]; Jan 21 [BH-D106:L3,L4,L5,L7]; Jan 26 [BH-D110:L3,L4,L5,L7] [BH-D111:L3,L4,L5,L6,L7] |
| Group | 5 | Jan 6 [BH-D004:L5,L6,L12,L14] [BH-D005:L9,L10]; Jan 12 [BH-D005:L9,L11] [BH-D009:L5,L6,L12,L14]; Jan 19 [BH-D101:L3,L4,L6,L10] [BH-D103:L5,L7]; Jan 22 [BH-D107:L4,L7,L8,L9] [BH-D108:L4,L8,L9]; Jan 29 [BH-D107:L4,L12,L13,L14] [BH-D108:L4,L8,L12] |
| Family | 2 | Jan 9 [BH-D007:L5,L6,L7,L9] [BH-D008:L5,L6,L8,L11]; Jan 30 [BH-D113:L3,L4,L5,L6,L7,L9] |
| **Total** | **12** | **5 + 5 + 2 sessions; 11 unique dates** |

**Counting safeguards.** The two clinicians’ January 9 entries document *one* family encounter, HG-E104, not two visits. [BH-D007:L6,L8,L18] [BH-D008:L6,L7,L11] The January 19 group roster’s original 11:30 departure was expressly corrected to 11:15; a copy received January 26 retransmitted the original roster and recorded no new visit. The individual session began at 11:15 and is separately countable. [BH-D103:L5,L7,L9,L11] [BH-D104:L8,L11,L14,L20] [BH-D105:L3,L5,L6]

Scheduled slots and nontherapeutic group breaks are not additional sessions: for example, the January 6 attendance roster records Rowan’s actual arrival and departure, while the facilitator records a break; the same distinction applies to January 12. [BH-D005:L9,L10,L11,L17] [BH-D004:L5,L12] [BH-D009:L6,L12] Records for the January 8 no-show, January 15 clinic-cancelled group, January 27 no-show, and January 28 cancellation do not establish attended therapy. [BH-D015:L4,L5,L6,L9,L11] [BH-D016:L5,L6,L7,L9,L11] [BH-D112:L18,L19,L20,L21,L22,L23,L25] [BH-D108:L4,L8,L11,L18] Medication visits, partner-only collateral contact, and care coordination are likewise outside this patient-attended therapy count. [BH-D010:L4,L5,L6,L7,L11,L17] [BH-D012:L4,L5,L6,L8,L11,L17] [BH-D109:L3,L4,L5,L6,L7,L13] [BH-D114:L3,L4,L5,L6,L12,L14,L15]

# Evidence

Original document lines referenced in the answer:

## BH-D002 — [intake_and_individual_jan05.txt](<../data/intake_and_individual_jan05.txt>)

```text
L0004 Harbor Grove Behavioral Health | Outpatient psychotherapy
L0005 Rowan Mercer | DOB 1991-04-12 | MRN HG-M042
L0006 Encounter HG-E101 | Service date 2026-01-05
L0008 Patient-present individual therapy: 09:00–09:50 local; completed, 50 minutes.
```

## BH-D004 — [group_facilitator_jan06.txt](<../data/group_facilitator_jan06.txt>)

```text
L0005 Service date 2026-01-06 | Group scheduled 10:00–11:30 local
L0006 Rowan Mercer | DOB 1991-04-12 | MRN HG-M042 | Encounter HG-E102
L0012 The whole group took a break from 10:45 to 11:00. No therapy was conducted during that interval. Following the break, the facilitator resumed with a paired planning exercise and a group discussion of barriers to practice at home. 
L0014 Rowan was quiet initially and responded when invited to identify a situation involving avoidance. They described delaying a reply to a work message because they feared being asked for a firm return date. Rowan practiced a breathing exercise and selected reading the message before deciding how to respond as a possible next step. Their participation was relevant to the topic, and they appeared receptive to peer suggestions. The patient attendance roster is maintained by the group desk.
```

## BH-D005 — [early_group_attendance_roster.txt](<../data/early_group_attendance_roster.txt>)

```text
L0009 Date       | Encounter | Scheduled slot | Patient arrived | Patient departed | Desk status
L0010 2026-01-06 | HG-E102   | 10:00–11:30    | 10:15           | 11:15            | Attended part
L0011 2026-01-12 | HG-E105   | 10:00–11:30    | 10:00           | 11:30            | Attended full
L0017 The desk records arrival and departure when members enter or leave the scheduled group. Session activities and room breaks are documented in the facilitator's record. Prepared from the signed reception attendance sheet for the two dates listed.
```

## BH-D007 — [family_primary_jan09.txt](<../data/family_primary_jan09.txt>)

```text
L0005 Rowan Mercer | DOB 1991-04-12 | MRN HG-M042
L0006 Encounter HG-E104 | 2026-01-09, 14:00–14:45 local
L0007 Present: Rowan and partner, Casey Mercer
L0008 Clinicians: Mara Voss, LCSW; cofacilitator Leena Park, LPC
L0009 Patient-present family therapy duration: 45 minutes
L0018 Plan: try the planned check-in and review its effect at the next individual visit. Continue the small activity steps selected in treatment. Leena Park's accompanying entry is filed under encounter HG-E104.
```

## BH-D008 — [family_cofacilitator_jan09.txt](<../data/family_cofacilitator_jan09.txt>)

```text
L0005 Rowan Mercer | DOB 1991-04-12 | MRN HG-M042
L0006 Encounter HG-E104 | Date 2026-01-09 | 14:00–14:45 local
L0007 Author: Leena Park, LPC, cofacilitator with Mara Voss, LCSW
L0008 Participants: Rowan Mercer and Casey Mercer; both present for the full 45 minutes
L0011 Accompanying clinical entry for the family appointment facilitated with Mara Voss. My role was to assist with communication practice and observe how the couple responded when slowing down an anxious exchange. Rowan initially described partner reminders as evidence that they were falling behind. Casey explained that the reminders were an attempt to help, while also recognizing that repeated prompts increased tension.
```

## BH-D009 — [group_facilitator_jan12.txt](<../data/group_facilitator_jan12.txt>)

```text
L0005 Rowan Mercer | DOB 1991-04-12 | MRN HG-M042 | Encounter HG-E105
L0006 Service date 2026-01-12 | Scheduled group 10:00–11:30 local
L0012 Group break: 10:40–10:55; no therapeutic activity occurred during the break. The second portion of the group included creating an activity ladder, anticipating obstacles, and rehearsing a neutral response to a missed attempt. Members were encouraged to specify the next action in concrete terms, including when and where it could take place.
L0014 Rowan contributed an example about leaving work messages unopened. They identified looking at one message as a lower step than replying to every outstanding message. They also described taking a walk with Casey over the weekend and noted that it helped the evening feel less dominated by worry. During the planning exercise, Rowan wrote down an action to try after breakfast and asked how to respond if the morning went poorly.
```

## BH-D010 — [medication_review_jan13.txt](<../data/medication_review_jan13.txt>)

```text
L0004 Harbor Grove Behavioral Health | Prescriber visit
L0005 Rowan Mercer | DOB 1991-04-12 | MRN HG-M042
L0006 Encounter HG-E106 | Date 2026-01-13
L0007 Actual visit 09:00–09:25 local; completed, 25 minutes
L0011 Rowan attended for medication management. The visit addressed medication use, tolerability, adherence, and symptom response relevant to the current prescription plan. Rowan reported continuing sleep interruption and daytime tiredness. They described mood as somewhat less heavy on days with a planned activity but remained concerned about work communication. The medication list was reviewed with Rowan and reconciled with the active chart.
L0017 Service documented: medication review and management only. No separate psychotherapy component was provided or documented. Rowan was directed to bring activity and communication concerns to the treating therapist for continued work.
```

## BH-D011 — [individual_therapy_jan14.txt](<../data/individual_therapy_jan14.txt>)

```text
L0004 Harbor Grove Behavioral Health | Individual psychotherapy
L0005 Rowan Mercer | DOB 1991-04-12 | MRN HG-M042
L0006 Encounter HG-E107 | Date 2026-01-14
L0007 Patient-present session 11:00–11:45 local; completed, 45 minutes
```

## BH-D012 — [partner_collateral_jan16.txt](<../data/partner_collateral_jan16.txt>)

```text
L0004 Harbor Grove Behavioral Health | Family collateral
L0005 Patient: Rowan Mercer | DOB 1991-04-12 | MRN HG-M042
L0006 Encounter HG-E109 | Date 2026-01-16 | 14:00–14:40 local
L0008 Participant: Casey Mercer, partner. Rowan was absent for the entire contact.
L0011 Casey attended the arranged contact after Rowan advised the office that they could not participate. Existing consent for partner involvement was confirmed in the chart. This was a collateral discussion with Casey only, focused on observations at home and ways to support the treatment plan.
L0017 Rowan did not join in person, by telephone, or by video. No patient-present psychotherapy occurred during this contact. Information from Casey will be incorporated into the next direct clinical review with Rowan. No new treatment decision was made with Rowan during this appointment.
```

## BH-D015 — [missed_visit_outreach_jan08.txt](<../data/missed_visit_outreach_jan08.txt>)

```text
L0004 Harbor Grove Behavioral Health | Scheduling support log
L0005 Rowan Mercer | DOB 1991-04-12 | MRN HG-M042
L0006 Related appointment: HG-E103, 2026-01-08, 11:00–11:45 local
L0009 11:12: Reception notified the clinician that Rowan had not checked in. There was no arrival call or cancellation message on the scheduling line. The appointment remained on the room schedule until its end time.
L0011 11:45: Appointment marked no show. Rowan was not seen for the scheduled individual visit.
```

## BH-D016 — [group_cancellation_notice_jan15.txt](<../data/group_cancellation_notice_jan15.txt>)

```text
L0005 Patient copy: Rowan Mercer | DOB 1991-04-12 | MRN HG-M042
L0006 Related encounter: HG-E108
L0007 Notice entered 2026-01-15, 08:12 local by N. Ellis
L0009 The coping skills group scheduled for January 15 from 10:00 to 11:30 is cancelled by the clinic because of staff illness. A covering facilitator is unavailable for this morning's group. The group room has been released from the schedule, and registered participants are being contacted before the planned start time.
L0011 08:15: Portal notice delivered to Rowan's account. The notice states that the office initiated the cancellation and that the participant should not come to the group room this morning.
```

## BH-D101 — [BH-D101_group_content_2026-01-19.txt](<../data/BH-D101_group_content_2026-01-19.txt>)

```text
L0003 Skills group clinical record | Service date: January 19, 2026
L0004 Group encounter: HG-E110 | Facilitator: Leah Chen, LCSW
L0006 Scheduled group: 10:00–11:30. Nontherapeutic break: 10:45–11:00.
L0010 Rowan initially followed the exercise and identified postponing a message to a supervisor as a familiar pattern. When discussion turned to returning to the workplace, Rowan became visibly tense and said the amount of discussion felt difficult to manage. The facilitator offered grounding and arranged a same-day individual meeting with the treating clinician. Patient-specific arrival and departure are maintained on the attendance roster.
```

## BH-D103 — [BH-D103_attendance_correction_2026-01-20.txt](<../data/BH-D103_attendance_correction_2026-01-20.txt>)

```text
L0005 Applies to group encounter HG-E110, service date January 19, 2026
L0007 Correction: Patient departure for HG-E110 is 11:15, replacing the original roster value of 11:30. Patient arrival remains 10:00.
L0009 During review of the same-day transfer, the original group roster was found to retain the scheduled group closing time in Rowan's departure field. The room-transfer record shows Rowan leaving skills room B at 11:15 and being received by the individual clinician at 11:15. I reviewed that record with the receiving clinician and confirm the corrected departure time above. The group continued for other members until its scheduled close.
L0011 This correction applies only to Rowan Mercer's departure field on the January 19 group attendance roster. It does not change the group service date, scheduled opening or closing, the break recorded in the group clinical note, or the separate individual appointment. The original signed roster is retained in the chart with this correction attached to its attendance entry.
```

## BH-D104 — [BH-D104_resent_roster_received_2026-01-26.txt](<../data/BH-D104_resent_roster_received_2026-01-26.txt>)

```text
L0008 The attached attendance sheet was resent following a request for the original group roster. The transmitted packet contains the cover sheet and the original patient-specific roster extract. No correction sheet was included in this transmission. Intake staff indexed the received copy under the service date printed on the roster. The receipt date is the inbox processing date.
L0011 Service date: January 19, 2026 | Group encounter: HG-E110
L0014 Patient arrival: 10:00 | Patient departure: 11:30 | Status: Attended
L0020 Records intake: indexed by Ana Reed, records assistant, January 26, 2026, 16:31. This is a retransmission of the January 19 roster for HG-E110. The received copy contains no new clinician signature and records no additional visit.
```

## BH-D105 — [BH-D105_individual_2026-01-19.txt](<../data/BH-D105_individual_2026-01-19.txt>)

```text
L0003 Individual psychotherapy | Encounter HG-E111
L0005 January 19, 2026 | In person
L0006 Patient contact: 11:15–11:45 | Completed: 30 minutes
L0009 This visit was added because Rowan became anxious during group and needed individual grounding and review of coping strategies. Rowan came directly from the group room. The patient described feeling overwhelmed when other members discussed workplace demands and worried that returning to work would expose difficulties keeping up. Rowan was able to identify muscle tension, rapid breathing, and an urge to leave as early signs of activation.
```

## BH-D106 — [BH-D106_telehealth_2026-01-21.txt](<../data/BH-D106_telehealth_2026-01-21.txt>)

```text
L0003 Individual psychotherapy | Encounter HG-E112 | Appointment HG-A112
L0004 Rowan Mercer | DOB: 1991-04-12 | MRN: HG-M042
L0005 January 21, 2026 | Video | Clinician: Mira Patel, LCSW
L0007 Patient contact occurred 13:00–13:20 and 13:30–13:55. Connection was lost from 13:20–13:30; there was no therapeutic contact during that interval. Total patient psychotherapy contact: 45 minutes. The reconnection continued the same clinical encounter under original appointment HG-A112.
```

## BH-D107 — [BH-D107_group_activity_records_2026-01-22_and_29.txt](<../data/BH-D107_group_activity_records_2026-01-22_and_29.txt>)

```text
L0004 Chart routing: Rowan Mercer | DOB: 1991-04-12 | MRN: HG-M042
L0007 January 22, 2026 | Encounter HG-E113
L0008 Scheduled group 10:00–11:30. Nontherapeutic break 10:45–11:00.
L0009 The session addressed translating a broad intention into one observable action. Members practiced reducing a complicated task to an action that could be completed in a few minutes and identifying the cue that would prompt it. Rowan joined the discussion after it had begun; the arrival field is maintained in the attendance register. Rowan used opening a work calendar as an example and described concern that seeing outstanding items would become overwhelming. Facilitator encouraged a limited, planned review period and a stopping point. The patient contributed an example to the discussion after the break.
L0012 January 29, 2026 | Encounter HG-E118
L0013 Scheduled group 10:00–11:30. Nontherapeutic break 10:45–11:00.
L0014 The session reviewed setbacks when practicing approach behaviors. Members identified an initial effort, what made follow-through difficult, and one adjustment for the next attempt. Rowan reported opening the work calendar but delaying a follow-up conversation. The facilitator helped identify a specific question to ask rather than trying to anticipate every possible concern. Rowan participated in the paired rehearsal and accepted feedback about keeping the request brief.
```

## BH-D108 — [BH-D108_final_attendance_and_cancellation_register.txt](<../data/BH-D108_final_attendance_and_cancellation_register.txt>)

```text
L0004 Rowan Mercer | DOB: 1991-04-12 | MRN: HG-M042
L0008 Service date | Encounter | Service | Scheduled | Actual arrival | Actual departure | Final disposition
L0009 January 22 | HG-E113 | Skills group | 10:00–11:30 | 10:30 | 11:30 | Attended, late arrival
L0011 January 28 | HG-E117 | Individual | 14:00–14:45 | — | — | Patient cancelled before appointment
L0012 January 29 | HG-E118 | Skills group | 10:00–11:30 | 10:00 | 11:30 | Attended
L0018 January 28 scheduling entry: Cancellation received from patient January 28, 08:12. Rowan reported a personal scheduling conflict. Appointment HG-E117 was cancelled before the scheduled start; no replacement appointment was booked within January 2026. Entered by Ana Reed, January 28, 08:18.
```

## BH-D109 — [BH-D109_care_coordination_2026-01-23.txt](<../data/BH-D109_care_coordination_2026-01-23.txt>)

```text
L0003 Care coordination | Encounter HG-E114
L0004 Rowan Mercer | DOB: 1991-04-12 | MRN: HG-M042
L0005 January 23, 2026 | 09:00–09:20
L0006 Participants: Mira Patel, LCSW, and Daniel Shaw, outside social worker
L0007 Patient participation: None. No patient contact occurred.
L0013 This contact was between professionals only. Rowan did not join by telephone or video, and no psychotherapy was delivered to the patient during the call. A brief coordination summary will be available to the treating team so that the patient is not asked to repeat administrative information unnecessarily.
```

## BH-D110 — [BH-D110_individual_primary_record_2026-01-26.txt](<../data/BH-D110_individual_primary_record_2026-01-26.txt>)

```text
L0003 Individual psychotherapy | Encounter HG-E115 | Appointment HG-A115
L0004 Rowan Mercer | DOB: 1991-04-12 | MRN: HG-M042
L0005 January 26, 2026 | In person
L0007 Actual patient psychotherapy contact: 09:00–09:50, 50 minutes.
```

## BH-D111 — [BH-D111_individual_second_record_2026-01-26.txt](<../data/BH-D111_individual_second_record_2026-01-26.txt>)

```text
L0003 Participating clinician psychotherapy record
L0004 Encounter HG-E115 | Appointment HG-A115 | Service date January 26, 2026
L0005 Rowan Mercer | DOB: 1991-04-12 | MRN: HG-M042
L0006 Service: Individual psychotherapy, in person
L0007 Actual patient psychotherapy contact: 09:10–09:50, 40 minutes.
```

## BH-D112 — [BH-D112_draft_note_and_charge_extract_2026-01-27.txt](<../data/BH-D112_draft_note_and_charge_extract_2026-01-27.txt>)

```text
L0018 SECTION B — POSTED CHARGE EXTRACT
L0019 Charge ID: CH-116 | Encounter: HG-E116
L0020 Service date: January 27, 2026 | Posting date: January 27, 2026, 18:06
L0021 Description: Group psychotherapy
L0022 Quantity charged: 1 group session
L0023 Charge status in this export: Posted
L0025 The charge row was exported from the billing work queue. This administrative extract preserves the draft document fields and posted charge fields as they appeared on January 30. The signed group attendance register is maintained in the clinical attendance section of the chart.
```

## BH-D113 — [BH-D113_family_therapy_2026-01-30.txt](<../data/BH-D113_family_therapy_2026-01-30.txt>)

```text
L0003 Family psychotherapy | Encounter HG-E119
L0004 Rowan Mercer | DOB: 1991-04-12 | MRN: HG-M042
L0005 January 30, 2026 | In person | Clinician: Mira Patel, LCSW
L0006 Therapist session interval: 13:00–13:45, 45 minutes.
L0007 Partner only: 13:00–13:15. Rowan present with partner: 13:15–13:45, 30 minutes.
L0009 Rowan's partner, Casey Mercer, arrived first. During the initial interval, Casey described uncertainty about when reminders helped and when they seemed to increase Rowan's sense of pressure. Rowan was not present for that portion. The discussion focused on Casey's observations and questions about supporting the agreed approach tasks.
```

## BH-D114 — [BH-D114_medication_management_2026-01-30.txt](<../data/BH-D114_medication_management_2026-01-30.txt>)

```text
L0003 Medication management | Encounter HG-E120
L0004 Rowan Mercer | DOB: 1991-04-12 | MRN: HG-M042
L0005 January 30, 2026 | 15:00–15:20 | Completed, 20 minutes
L0006 Prescriber: Elena Ortiz, PMHNP
L0012 The service consisted of medication evaluation and management, including symptom review and medication counseling. No separately documented psychotherapy was provided. Ongoing psychotherapy goals and behavioral assignments remain with the treating therapist. Rowan agreed to continue attending scheduled outpatient follow-up and to bring questions about the medication regimen to the next medication appointment.
L0014 Electronically signed: Elena Ortiz, PMHNP | January 30, 2026, 16:02
L0015 Record status: Final
```

# Run information

- Online model calls: 4
