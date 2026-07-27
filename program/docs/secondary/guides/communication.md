# Communication Domain Guide

**Secondary School Management System**
Last Updated: March 2026

---

## Overview

The Communication domain covers 6 modules for messaging, notifications, event coordination, and parent engagement. All data is stored in `secondary_school.db`.

---

## Email

Send and manage email communications to staff, students, and parents.

- Compose and send emails to individuals or groups
- Recipient groups: by year group, form group, class, role, or custom list
- Template library: pre-built templates for common communications (absence follow-up, event invitations, report distribution)
- Email history: searchable log of all sent emails with timestamp and recipients
- Attachments: include documents, letters, or reports
- Draft saving: compose and send later
- Delivery tracking: sent, delivered, bounced
- Reply management: inbound replies linked to original message
- Bulk email with merge fields: student name, form group, year group

| Field | Description |
|---|---|
| To | Individual email or recipient group |
| Subject | Email subject line |
| Body | Message content (rich text) |
| Attachments | Optional file attachments |
| Template | Optional pre-built template |
| Schedule | Send now or schedule for later |

### Common Email Templates

| Template | Purpose | Typical Recipients |
|---|---|---|
| Absence Notification | Inform parents of unexplained absence | Parent/carer |
| Detention Notice | 24-hour notice for after-school detention | Parent/carer |
| Report Distribution | Accompany termly report cards | Parent/carer |
| Event Invitation | Invite to school events | Parents, students |
| Staff Bulletin | Weekly staff updates | All staff |
| Trip Letter | Trip details and consent request | Parents of attendees |

## Notifications

In-app notifications for system events and alerts.

- Automatic notifications triggered by system events
- Notification types: info, warning, action required, reminder
- Delivered within the GUI via notification panel
- Mark as read, dismiss, or action
- Notification preferences: users can configure which alerts they receive
- Unread notification count displayed in the sidebar
- Notification history: searchable log of past notifications

| Trigger Event | Notification Sent To |
|---|---|
| Homework set | Students in class |
| Homework overdue | Student, form tutor |
| Attendance below 90% | Head of Year, form tutor |
| Behaviour incident logged | Form tutor, Head of Year |
| Detention assigned | Student, parent (via email) |
| Exam entry created | Student |
| Report published | Student, parent |
| Safeguarding concern | DSL |
| Policy review due | Policy owner |
| DBS expiry approaching | HR admin |

## Announcements

Publish school-wide or targeted announcements.

- Create announcements with title, content, and target audience
- Target by: whole school, year group, form group, staff only, students only
- Display priority: normal, important, urgent
- Scheduled publishing: set start and end dates for time-limited announcements
- Pin important announcements to the top of the feed
- Announcement feed visible on the dashboard after login
- Archive expired announcements automatically
- Attachments: include supporting documents or images

| Priority | Display | Example |
|---|---|---|
| Normal | Standard feed item | Club schedule changes |
| Important | Highlighted in feed | Parent evening booking open |
| Urgent | Banner at top of dashboard | School closure due to weather |

## Calendar

Manage the school calendar with term dates, events, and INSET days.

- **Term dates**: display current academic year term and half-term dates
- **INSET days**: mark non-pupil staff training days
- **Events**: add school events with date, time, location, and description
- Event categories: academic, sport, performing arts, careers, community, governance
- Recurring events: weekly assemblies, monthly governor meetings
- Calendar views: day, week, month, term, full year
- Filter by category or year group
- Export calendar to iCal format
- Public calendar view for parents (configurable)
- Link events to relevant modules (e.g. trips, parents' evening, exams)

| Calendar Entry Type | Description |
|---|---|
| Term Start / End | First and last day of each term |
| Half-term | Holiday weeks within terms |
| INSET Day | Staff training, no students |
| Bank Holiday | National holidays |
| Exam Period | Internal or external exam windows |
| School Event | Concerts, sports day, open evening |
| Deadline | Application or submission deadlines |

### Typical Academic Year Calendar

| Period | Approximate Timing |
|---|---|
| Autumn Term | September - December |
| Spring Term | January - March/April |
| Summer Term | April - July |
| INSET Days | 5 per year (school-defined) |
| Year 11 Study Leave | May - June |
| GCSE Exams | May - June |
| Results Day | August |

## Parents' Evening

Manage parents' evening scheduling with time-slot booking.

### Setup
- Create parents' evening events: date, start/end time, appointment length
- Assign participating teachers (typically all subject teachers for a year group)
- Define time slots per teacher (e.g. 5-minute slots from 4:00 to 7:00 PM)
- Set booking open and close dates

### Booking
- Parents book appointments with their child's teachers via the system
- Automatic clash prevention: no overlapping appointments for the same parent or teacher
- Gap slots: optional breaks between appointments for teacher comfort
- Priority booking: option to give certain groups early access (e.g. SEN, PP)
- Booking confirmation sent via email or notification

### On the Evening
- Print appointment schedules per teacher
- Print parent itinerary with appointment times and room locations
- Running order display for reception area
- Record attendance: mark which parents attended

### Reporting
- Attendance statistics: percentage of parents who attended
- Non-attendance follow-up: list of parents who did not book or attend
- Export appointment data for pastoral follow-up

| Field | Description |
|---|---|
| Event Name | e.g. Year 9 Parents' Evening |
| Date | Date of the event |
| Time Window | e.g. 16:00 - 19:00 |
| Slot Duration | e.g. 5 minutes |
| Teachers | Staff participating |
| Booking Opens | Date parents can start booking |
| Booking Closes | Deadline for bookings |

## Communication Log

Record and track all contact with parents and carers.

- Log phone calls, meetings, emails, and letters with parents/carers
- Record: date, time, staff member, parent/carer, student, contact method, summary
- Categorise contacts: attendance, behaviour, academic progress, welfare, general
- Flag follow-up actions with due dates and assigned staff
- View communication history per student or per parent
- Search logs by date, staff member, category, or student
- Link log entries to related records (behaviour incidents, attendance concerns, SEN reviews)
- Generate communication reports for pastoral meetings
- Evidence trail for Ofsted, safeguarding, and complaints

| Field | Description |
|---|---|
| Date / Time | When the contact occurred |
| Staff Member | Who made or received the contact |
| Parent / Carer | Name of parent/carer contacted |
| Student | Related student (SEC ID) |
| Method | Phone, email, meeting, letter, home visit |
| Category | Attendance, behaviour, academic, welfare, general |
| Summary | Brief description of the contact |
| Follow-Up | Actions agreed, with due date |
| Outcome | Resolved, ongoing, escalated |

---

## Cross-System Messaging

Secondary school staff often need to coordinate with colleagues at the
feeder primary school (sending students up) or the receiving sixth-form
college (transitions out). The **Cross-System Messaging** feature is
embedded directly into the Secondary School Email screen and Email CLI
sub-menu so you don't have to leave your inbox to talk to staff in
Primary, College, or University.

### Where to find it

| Interface | Location |
|-----------|----------|
| GUI | **Communication → Email**, then the **Cross-System** tab |
| CLI | **Communication → Email → 2) Cross-System Messages** |

### What it does

| Tab / option | Purpose |
|---|---|
| Inbox | Messages other systems' staff have sent to you. Sender, system, subject, related student, date, read state. |
| Sent | Messages you've sent to other systems. |
| Compose | Pick the target system (Primary / Secondary / College / University), then a recipient from that system's staff list, optionally tag a student name, then enter subject + body. |

Messages are stored centrally in `auth.db` (`cross_system_messages`
table) so the recipient sees them from whichever system they log into.

### Service reference

| Method | Purpose |
|--------|---------|
| `InterSystemMessagingService.send_message` | Send a message to a staff member in another system |
| `InterSystemMessagingService.get_inbox` | Retrieve messages received from other systems |
| `InterSystemMessagingService.get_sent` | Retrieve messages sent to other systems |
| `InterSystemMessagingService.get_staff_list(system)` | List staff in a target system for the recipient picker |
| `InterSystemMessagingService.search_messages` | Search inbox + sent by subject, body, or student name |

The reusable GUI panel lives in
`education_system.shared.messaging.cross_system_panel` and the CLI in
`education_system.shared.messaging.cross_system_cli`.

---

## Idle / inactivity auto-logout

The Secondary School GUI and CLI both auto-log-out after **30 minutes
of inactivity** to reduce the risk of an unattended terminal exposing
student data.

| Interface | How activity is tracked |
|-----------|-------------------------|
| GUI | Mouse motion, key presses, mouse buttons, and scroll-wheel events on the main window reset the idle timer. |
| CLI | The menu prompt is wrapped in a `SIGALRM` watchdog that fires after 30 minutes of no input. |

When the timeout fires, the GUI shows a `Session Expired` warning then
returns the user to the universal login screen; the CLI prints
`⚠ Logged out after 30 minutes of inactivity.` and exits cleanly.

To change the default, edit the `attach_idle_timeout(self, ..., timeout_minutes=30)`
call in `secondary_school/main_gui.py` or the
`enable_idle_timeout(30, ...)` call in `secondary_school/cli/cli_main.py`.

See `docs/secondary/security/SESSION_TIMEOUT.md` for the full
configuration and security rationale.

---

## Access by Role

| Module | Admin | Teacher | Student |
|---|---|---|---|
| Email | Full access | Send to own classes/parents | No access |
| Cross-System Messaging | Full access | Send to staff in any other system | No access |
| Notifications | Full access | Receive and manage own | Receive and manage own |
| Announcements | Full CRUD | View all, create for own classes | View targeted |
| Calendar | Full CRUD | View all, add class events | View all |
| Parents' Evening | Full CRUD | View own schedule | View appointments |
| Communication Log | Full access | Log and view own contacts | No access |

---

*Secondary School Management System -- Communication Domain Guide*
