# Primary School — Facilities Guide

> Covers 4 modules: Room Booking, Assets, Visitors, Incidents

Last Updated: March 2026

---

## Room Booking

Book rooms and shared spaces across the school.

### Bookable Spaces

| Space Type | Examples |
|---|---|
| Classrooms | Individual classrooms when not timetabled |
| Hall | Main hall, dining hall |
| Meeting Rooms | Staff room, conference room, SLT office |
| Specialist Rooms | ICT suite, music room, art room, library |
| Outdoor | Playground, field, MUGA, forest school area |

### Making a Booking

1. Navigate to Room Booking tab.
2. Select the space from the dropdown.
3. Choose the date and time slot.
4. Enter the purpose (e.g., "Year 4 rehearsal", "Parent meeting", "Staff training").
5. Check availability — the system shows any conflicts.
6. Confirm the booking.

### Key Features

- **Calendar view** — View all bookings for a space on a daily, weekly, or monthly calendar.
- **Availability checker** — Search for available spaces across a date/time range.
- **Recurring bookings** — Set up weekly or fortnightly recurring bookings (e.g., weekly assembly slot).
- **Clash detection** — The system prevents double-booking. Timetabled lessons are blocked automatically.
- **Cancellation** — Cancel a booking with an optional reason. Recurring bookings can be cancelled individually or as a series.
- **Reports** — Room utilisation reports showing usage by space, time, and purpose.

### Booking Rules

- Bookings require a minimum lead time (configurable, default: same day).
- Maximum booking duration is configurable (default: full day).
- Some spaces may require admin approval before confirmation.

---

## Assets

Maintain an inventory of school assets and equipment.

### Asset Register

| Field | Description |
|---|---|
| Asset ID | Auto-generated unique identifier |
| Name | Description of the asset |
| Category | ICT, Furniture, PE Equipment, AV, Musical Instruments, Books, Other |
| Location | Where the asset is stored/located |
| Purchase Date | When it was acquired |
| Purchase Cost | Original cost |
| Supplier | Where it was purchased |
| Condition | New, Good, Fair, Poor, Disposed |
| Assigned To | Room, department, or staff member |
| Serial Number | For electronic equipment |
| Warranty Expiry | End of warranty period |

### Key Workflows

- **Add an asset** — Enter details when new equipment is purchased. Link to a Finance transaction if applicable.
- **Update condition** — Periodically review and update asset condition. Schedule replacement for items in Poor condition.
- **Dispose of an asset** — Mark as Disposed with date and reason (broken, obsolete, donated). Asset remains in the register for audit purposes.
- **Stock check** — Generate a stock check list by location or category. Mark items as verified, missing, or damaged.
- **Transfer** — Move an asset between locations or reassign to a different staff member.

### Reports

- Full asset register (filterable by category, location, condition).
- Assets approaching warranty expiry.
- Disposal log.
- Total asset value by category.

---

## Visitors

Manage visitor access to the school site with safeguarding compliance.

### Visitor Sign-In

| Field | Description |
|---|---|
| Visitor Name | Full name |
| Organisation | Company, agency, or parent |
| Purpose | Reason for visit |
| Visiting | Staff member or department being visited |
| DBS Status | Yes (verified), No, N/A (escorted at all times) |
| Badge Issued | Visitor badge number |
| Time In | Sign-in time |
| Time Out | Sign-out time |

### Sign-In Workflow

1. Visitor arrives at reception.
2. Enter visitor details in the system.
3. Check DBS status:
   - **DBS verified** — Issue a green safeguarding badge (unsupervised access permitted).
   - **No DBS** — Issue a red badge (must be escorted at all times).
4. Print visitor badge (optional).
5. Visitor signs out on departure — Time Out is recorded.

### Key Features

- **Live register** — View all visitors currently on site in real time.
- **Pre-registration** — Pre-register expected visitors (e.g., for parents' evening, governor visits) to speed up sign-in.
- **Returning visitors** — The system remembers previous visitors. Auto-fill details for known visitors.
- **DBS verification** — Record DBS certificate numbers for regular visitors (governors, volunteers, contractors).
- **Emergency evacuation** — Generate a list of all visitors currently on site for fire evacuation roll call.
- **Reports** — Visitor frequency reports, DBS compliance summary.

### Safeguarding Requirements

- All visitors must sign in and out.
- Visitors without DBS clearance must be escorted at all times.
- Visitor data is retained for the configured period (default: 1 academic year).

---

## Incidents

Record and manage incidents, accidents, and near-misses.

### Incident Types

| Type | Description |
|---|---|
| Accident | Physical injury to a pupil, staff member, or visitor |
| Near Miss | An event that could have resulted in injury |
| Property Damage | Damage to school property or equipment |
| Security | Unauthorised access, theft, vandalism |
| Environmental | Flooding, structural issues, hazardous materials |

### Incident Record

| Field | Description |
|---|---|
| Date/Time | When the incident occurred |
| Location | Where it happened |
| Type | Accident, near miss, property damage, security, environmental |
| People Involved | Pupils, staff, visitors involved |
| Description | Full account of what happened |
| Injuries | Description of any injuries sustained |
| First Aid | First aid administered (links to Medical module) |
| Witnesses | Names of witnesses |
| Reported By | Staff member recording the incident |
| Severity | Minor, Moderate, Serious, Critical |

### Follow-Up Actions

- Record actions taken to prevent recurrence.
- Assign follow-up tasks to specific staff members with deadlines.
- Track completion of follow-up actions.
- Link to risk assessments if the incident reveals a new hazard.

### RIDDOR Reporting

- For serious incidents, the system flags whether a RIDDOR report is required (Reporting of Injuries, Diseases and Dangerous Occurrences Regulations).
- Generate RIDDOR-formatted reports for submission to HSE.

### Key Workflows

1. **Record incident** — Enter all details as soon as possible after the event.
2. **Notify** — For pupil injuries, notify parents. For serious incidents, notify the headteacher and governors.
3. **Follow up** — Assign and track corrective actions.
4. **Review** — Periodically review incident patterns to identify recurring hazards.

### Reports

- Incident summary by type, location, and severity.
- Trend analysis (monthly/termly comparisons).
- Outstanding follow-up actions.
- RIDDOR-reportable incidents log.

---

## Quick Reference

| Module | Access Path | Key Roles |
|---|---|---|
| Room Booking | Sidebar → Facilities → Room Booking | admin, teacher |
| Assets | Sidebar → Facilities → Assets | admin |
| Visitors | Sidebar → Facilities → Visitors | admin |
| Incidents | Sidebar → Facilities → Incidents | admin, teacher |
