# Pastoral Care Domain Guide

**Secondary School Management System**
Last Updated: March 2026

---

## Overview

The Pastoral Care domain covers 7 modules for behaviour management, safeguarding, rewards, and special educational needs across Years 7-11. Safeguarding records have restricted access controls. All data is stored in `secondary_school.db`.

---

## Behaviour

Log and monitor behaviour incidents across the school.

- Record positive and negative behaviour incidents with date, time, location, and description
- Categorise incidents: disruption, defiance, bullying, fighting, positive contribution, excellent work
- Assign behaviour points (positive or negative) per incident
- Link incidents to specific lessons, subjects, or general school time
- Pattern detection: flag students with recurring incidents by type, time, or location
- View behaviour history per student, form group, or year group
- Generate behaviour summary reports for SLT and pastoral meetings

| Point Type | Examples |
|---|---|
| Positive (+) | Excellent work, helping others, outstanding effort |
| Negative (-) | Disruption, lateness to lesson, failure to follow instructions |
| Serious (-) | Fighting, bullying, damage to property |

## Detentions

Schedule and track detentions with escalation pathways.

| Detention Type | Timing | Set By |
|---|---|---|
| Break | During break time | Any teacher |
| Lunchtime | During lunch period | Any teacher |
| After-school | After school hours (requires 24h parent notice) | Head of Year / SLT |
| Saturday | Weekend detention | SLT only |

- Create detentions linked to behaviour incidents
- Automatic parent notification for after-school and Saturday detentions
- Track detention attendance: attended, missed, rescheduled
- Escalation rules: missed detentions trigger next-level sanction
- View detention schedule by date, room, or supervising staff
- Bulk detention setting for class-wide incidents

## Exclusions

Manage fixed-term and permanent exclusions with statutory requirements.

- **Fixed-term exclusion**: record dates, duration (max 45 days per year), reason
- **Permanent exclusion**: full documentation, governors' panel scheduling
- Record reintegration meetings with date, attendees, and agreed actions
- Track cumulative exclusion days per student per academic year
- Generate exclusion letters (template-based)
- Link exclusions to behaviour incident records
- Governors' discipline panel: schedule hearings, record outcomes
- Local authority notification tracking for permanent exclusions

## Rewards

Recognise and celebrate student achievement.

- Award merit/reward points linked to categories: academic, effort, citizenship, sport
- House points system: aggregate points by house for inter-house competition
- Certificate generation: bronze, silver, gold, platinum thresholds
- Prize event management: nominations, shortlisting, award ceremonies
- Reward shop: students can view their point balance
- Leaderboards by form group, year group, or house
- Half-termly and termly reward summaries

| Threshold | Points Required | Award |
|---|---|---|
| Bronze | 50 | Certificate |
| Silver | 100 | Certificate + prize |
| Gold | 200 | Certificate + prize + letter home |
| Platinum | 500 | Headteacher's award |

## Pastoral

Record pastoral information and wellbeing concerns.

- Pastoral notes: confidential records by form tutors and Heads of Year
- Log wellbeing concerns: anxiety, friendship issues, family circumstances, bereavement
- Key contacts: record important external contacts (social workers, family support workers)
- Tutor meeting records: date, discussion points, agreed actions
- Vulnerable student flags visible to relevant staff
- Transition notes for students moving between year groups
- Link to Safeguarding module for concerns that meet the threshold

## Safeguarding

Log and manage safeguarding concerns with restricted access.

**Access is restricted to Designated Safeguarding Lead (DSL) and deputies only.**

- Log concerns with date, time, reporter, child's account, and actions taken
- Chronology view: full timeline of all concerns and actions per student
- Category classification: neglect, physical abuse, emotional abuse, sexual abuse, exploitation, radicalisation
- Multi-agency referral tracking: MASH referrals, Early Help assessments
- Record professional meetings: strategy meetings, child protection conferences
- Upload supporting documents (restricted storage)
- Body map tool for recording visible injuries
- DSL dashboard: open cases, pending actions, overdue reviews
- Audit trail: all access and edits logged with timestamp and user

| Access Level | Can View | Can Edit |
|---|---|---|
| DSL / Deputy DSL | All records | All records |
| Headteacher | All records | None |
| Class teacher | Report concern only | Own reports only |
| Admin / Student | No access | No access |

## SEND (Special Educational Needs and Disabilities)

Manage the SEN register, provisions, and statutory processes.

- **SEN Register**: record SEN status per student
  - K: SEN Support
  - E: Education, Health and Care Plan (EHCP)
- Primary need categories: cognition and learning, communication and interaction, SEMH, sensory/physical
- EHCP tracking: application dates, annual review dates, outcomes, provision details
- Provision mapping: record interventions, hours, staff, and cost
- Review scheduling: termly SEN reviews, annual EHCP reviews
- Exam access arrangements: extra time (25%), rest breaks, reader, scribe, modified papers
- Link access arrangements to Exams module for exam entries
- One-page student profiles: strengths, difficulties, strategies for teachers
- Generate SEN reports for governors and local authority

---

## Escalation Pathway

Behaviour incidents follow a structured escalation:

1. Verbal warning (logged)
2. Behaviour point recorded
3. Break or lunchtime detention
4. After-school detention (with parental notice)
5. Head of Year involvement and pastoral support
6. SLT involvement and potential fixed-term exclusion
7. Governors' panel for persistent or serious incidents
8. Permanent exclusion (last resort)

---

## Access by Role

| Module | Admin | Teacher | Student |
|---|---|---|---|
| Behaviour | Full access | Log and view own classes | View own record |
| Detentions | Full CRUD | Set and manage own | View own |
| Exclusions | Full CRUD | View only | View own |
| Rewards | Full CRUD | Award points | View own balance |
| Pastoral | Full access | Own tutor group | No access |
| Safeguarding | DSL only | Report concerns | No access |
| SEND | Full access | View student profiles | No access |

---

*Secondary School Management System -- Pastoral Care Domain Guide*
