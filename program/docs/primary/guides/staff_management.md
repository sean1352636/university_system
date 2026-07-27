# Primary School — Staff Management Guide

> Covers 4 modules: HR, CPD, Cover, Staff Directory

Last Updated: March 2026

---

## HR (Human Resources)

Manage staff records, contracts, and statutory compliance.

### Staff Records

Each staff member is assigned a unique **STF-prefixed ID** (STF0001, STF0002, etc.).

| Field | Description |
|---|---|
| Staff ID | Auto-generated STF prefix |
| Name | Full name |
| Role | Teacher, Teaching Assistant, Admin, Site Staff, Midday Supervisor, etc. |
| Contract Type | Permanent, Fixed-term, Supply, Volunteer |
| Start Date | Employment start date |
| End Date | For fixed-term contracts |
| FTE | Full-time equivalent (1.0 = full time) |
| Pay Scale | Main Pay Range, Upper Pay Range, Leadership, Support Staff scales |
| Contact Details | Phone, email, emergency contact |

### DBS Checks

- Record DBS certificate number, issue date, and level (Enhanced, Enhanced with Barred List).
- Set renewal reminders.
- Flag expired or missing DBS checks on the dashboard.

### Single Central Record (SCR)

The SCR is a statutory requirement. The system maintains it automatically from staff data:

| SCR Check | Required For |
|---|---|
| DBS Enhanced | All staff |
| Barred List Check | All staff working with children |
| Right to Work | All staff |
| Identity Verification | All staff |
| Qualifications | Teachers (QTS) |
| Prohibition Check | Teachers |
| Overseas Check | Staff who have lived abroad |
| References | All staff (minimum 2) |

- View the SCR as a filterable table.
- Export as CSV or PDF for Ofsted inspection.
- Missing checks are highlighted in red.

### Common Workflows

- **Add staff member** — Navigate to HR tab, click Add Staff, complete all fields.
- **Record a DBS check** — Open staff record, go to Checks section, enter DBS details.
- **Generate SCR** — Click Export SCR to produce the current single central record.
- **Manage leavers** — Set an end date, record reason for leaving, archive the record.

---

## CPD (Continuing Professional Development)

Track training, professional development, and qualifications for all staff.

### Training Records

| Field | Description |
|---|---|
| Course/Activity | Name of the training |
| Provider | Internal, external provider, or online platform |
| Date | Date(s) of training |
| Duration | Hours or days |
| Category | Safeguarding, First Aid, Subject Knowledge, Leadership, SEND, ICT, etc. |
| Cost | Training cost (links to Finance module) |
| Certificate | Upload or reference certificate |
| Staff Member | Who attended |

### Key Workflows

- **Log training** — Select staff member, enter course details, attach certificate if available.
- **Plan CPD** — Schedule upcoming training and assign staff. Set reminders.
- **Mandatory training** — The system tracks statutory training requirements:
  - Safeguarding refresher (annual)
  - First Aid (3-year renewal)
  - Fire safety (annual)
  - Prevent training
- **Reports** — View CPD summary by staff member, category, or date range. Identify gaps in training.
- **Budget tracking** — CPD costs feed into the Finance module for budget monitoring.

---

## Cover

Manage staff absence and cover arrangements.

### Absence Recording

| Field | Description |
|---|---|
| Staff Member | The absent staff member |
| Date(s) | Single day or date range |
| Reason | Illness, personal, training, appointment, other |
| Cover Type | Internal cover, supply teacher, class split |

### Cover Arrangements

- **Internal cover** — Assign another teacher or TA to cover the class.
- **Supply teacher** — Record supply teacher details (name, agency, DBS status).
- **Class split** — Distribute pupils across other classes when no cover is available. The system suggests balanced splits.

### Key Workflows

1. **Record absence** — Open Cover tab, select staff member, enter dates and reason.
2. **Arrange cover** — Choose cover type and assign the covering staff member or supply teacher.
3. **Notify** — The system can generate a cover notification for the covering teacher with class details, timetable, and lesson plans.
4. **Reports** — Track absence patterns, cover costs, and supply usage over time.

### Supply Teacher Management

- Maintain a list of preferred supply teachers with contact details and DBS status.
- Record supply teacher bookings and costs.
- Rate supply teachers for future reference.

---

## Staff Directory

A searchable directory of all staff members.

### Directory Information

| Field | Visible To |
|---|---|
| Name | All staff |
| Role/Title | All staff |
| Department/Year Group | All staff |
| Email | All staff |
| Phone (school) | All staff |
| Phone (personal) | Admin only |
| Qualifications | Admin, self |
| Photo | All staff |

### Features

- **Search** — Find staff by name, role, department, or year group.
- **Filter** — Filter by role (teacher, TA, admin, site) or employment status (current, left).
- **Contact cards** — Click a staff member to view their full contact card.
- **Organisation chart** — View the school staffing structure showing reporting lines.
- **Export** — Export the directory as CSV for mail merges or external use.

---

## Quick Reference

| Module | Access Path | Key Roles |
|---|---|---|
| HR | Sidebar → Staff → HR | admin |
| CPD | Sidebar → Staff → CPD | admin, teacher (own records) |
| Cover | Sidebar → Staff → Cover | admin |
| Staff Directory | Sidebar → Staff → Directory | admin, teacher |
