# Facilities Domain Guide

**Secondary School Management System**
Last Updated: March 2026

---

## Overview

The Facilities domain covers 5 modules for managing school rooms, equipment, classroom layouts, visitor access, and incident reporting. All data is stored in `secondary_school.db`.

---

## Room Booking

Reserve rooms and spaces for activities beyond timetabled lessons.

- Book rooms for meetings, events, clubs, exams, and interventions
- View room availability by date, time, and capacity
- Recurring bookings: weekly meetings, regular clubs
- Room details: name, building, floor, capacity, facilities (projector, whiteboard, computers)
- Clash prevention: prevents double-booking against timetable and other bookings
- Approval workflow for high-demand rooms (e.g. hall, sports hall)
- Cancel and amend bookings with notification to affected staff
- Calendar view: daily, weekly, and monthly room usage

| Field | Description |
|---|---|
| Room Name | e.g. Main Hall, ICT Suite 1, Science Lab 3 |
| Building | Building or block identifier |
| Capacity | Maximum occupancy |
| Facilities | Equipment and features available |
| Availability | Hours available for booking |
| Timetabled | Whether used for regular lessons |

### Room Categories

| Category | Examples |
|---|---|
| Classrooms | Standard teaching rooms |
| Specialist | Science labs, ICT suites, DT workshops, art rooms |
| Sports | Sports hall, gymnasium, playing fields |
| Assembly | Main hall, drama studio |
| Meeting | Conference rooms, offices |
| Other | Library, dining hall, medical room |

## Assets

Track school equipment, furniture, and IT inventory.

- Register assets with unique ID, description, category, and location
- Record purchase details: date, cost, supplier, warranty expiry
- Track asset location: room, department, or staff member
- Asset status: in use, in storage, under repair, disposed
- Scheduled maintenance and service records
- Depreciation tracking for financial reporting
- Barcode or QR code labelling support
- Stocktake tools: mark assets as verified during audits
- Generate asset registers filtered by category, location, or department
- Disposal workflow: record reason, method, and authorisation

| Asset Category | Examples |
|---|---|
| IT Equipment | Laptops, desktops, tablets, projectors |
| Furniture | Desks, chairs, shelving, lockers |
| Science | Microscopes, lab equipment, chemicals |
| Sports | Gym mats, goals, rackets, balls |
| Music | Instruments, amplifiers, stands |
| General | Printers, photocopiers, whiteboards |

| Status | Description |
|---|---|
| In Use | Currently deployed and operational |
| In Storage | Available but not currently deployed |
| Under Repair | Being repaired or serviced |
| On Loan | Temporarily assigned to staff/student |
| Disposed | Written off, recycled, or sold |

## Seating Plans

Create and manage classroom seating arrangements.

- Create seating plans per room with a grid-based layout editor
- Assign students to specific seats within the grid
- Teacher-defined arrangements: rows, groups, horseshoe, paired, exam layout
- Store multiple plans per room (different classes use different layouts)
- Display key student information on the plan: SEN, PP, behaviour notes, target grades
- Colour coding by data: attainment level, SEN status, behaviour points
- Drag-and-drop seat reassignment in the GUI
- Print seating plans for classroom display or supply teacher reference
- Copy and adapt plans between classes or terms
- Link to student photos for visual identification

| Layout Style | Description |
|---|---|
| Rows | Traditional forward-facing rows |
| Groups | Cluster desks for group work (4-6 per group) |
| Horseshoe | U-shape arrangement facing the front |
| Paired | Two students per desk, forward-facing |
| Exam | Individual desks, spaced apart |

## Visitors

Manage visitor sign-in, safeguarding checks, and access control.

- Digital sign-in: record visitor name, organisation, purpose, host staff member
- Sign-in and sign-out timestamps
- Issue visitor badges with unique ID
- DBS check verification: record whether visitor holds a current DBS
- Safeguarding protocol: visitors without DBS must be escorted at all times
- Contractor management: record contractor details, risk assessments, site rules acknowledgement
- Pre-registered visitors: staff can pre-book expected visitors
- Emergency evacuation list: real-time count of visitors on site
- Visitor history: searchable log of all visits by date or visitor name
- Print visitor reports for safeguarding audits

| Visitor Type | DBS Required | Escort Required |
|---|---|---|
| Parent / Carer | No | No (in reception areas) |
| Governor | Yes (on SCR) | No |
| External Professional | Verify before entry | If no DBS |
| Contractor | Verify before entry | If no DBS |
| Guest Speaker | Verify before entry | If no DBS |
| Student (other school) | N/A | Yes |

### Sign-In Process
1. Visitor arrives at reception
2. Record name, organisation, purpose of visit, and host staff member
3. Verify DBS status (if applicable)
4. Issue visitor badge
5. Visitor reads safeguarding information
6. Host staff member notified
7. Visitor signs out on departure, returns badge

## Incidents

Report and track accidents, injuries, and near-misses.

- Log incidents with date, time, location, and description
- Record people involved: students, staff, visitors
- Categorise: accident, injury, near-miss, property damage, medical emergency
- Injury details: body part affected, severity, first aid administered
- Witness statements and staff on scene
- RIDDOR reporting: flag incidents reportable to HSE
- Investigation records: root cause, contributing factors
- Actions taken: immediate response and longer-term preventive measures
- Follow-up tracking: monitor recovery, check actions completed
- Generate incident reports for governors and health and safety committee
- Trend analysis: identify patterns by location, time, or type

| Severity | Description | Action |
|---|---|---|
| Minor | Small cuts, bumps, grazes | First aid, log, notify parents |
| Moderate | Sprains, significant cuts, head bumps | First aid, log, notify parents, monitor |
| Serious | Fractures, concussion, significant injury | First aid, log, notify parents, medical referral |
| Major | Life-threatening or RIDDOR-reportable | Emergency services, RIDDOR report, full investigation |

### Incident Report Fields

| Field | Description |
|---|---|
| Incident ID | Auto-generated unique reference |
| Date / Time | When the incident occurred |
| Location | Room, corridor, playground, off-site |
| Category | Accident, injury, near-miss, damage |
| People Involved | Names and roles (student/staff/visitor) |
| Description | What happened |
| Injury Details | Nature and severity of any injury |
| First Aid Given | Treatment administered |
| Staff Attending | Who responded to the incident |
| Witnesses | Names and statements |
| RIDDOR Reportable | Yes / No |
| Follow-Up Actions | Preventive measures and review dates |

---

## Access by Role

| Module | Admin | Teacher | Student |
|---|---|---|---|
| Room Booking | Full CRUD | Book rooms | No access |
| Assets | Full CRUD | View / request | No access |
| Seating Plans | Full CRUD | Create for own classes | No access |
| Visitors | Full CRUD | Pre-register visitors | No access |
| Incidents | Full CRUD | Report and view own | No access |

---

*Secondary School Management System -- Facilities Domain Guide*
