# Communication Guide

This guide covers the messaging, notifications, announcements, parent portal, parents' evening, document hub, letter templates, SMS/email, activity feed, and forums modules within the Sixth Form College Management System.

## Overview

The communication suite provides multiple channels for staff, students, and parents to exchange information. Each module serves a distinct communication purpose, from one-to-one messaging to college-wide announcements.

| Module | Audience | Direction |
|--------|----------|-----------|
| `messaging` | Staff, Students | Bidirectional (one-to-one) |
| `notifications` | All users | System to user |
| `announcements` | All users | Staff to audience groups |
| `parent_portal` | Parents/carers | View-only with linked student data |
| `parents_evening` | Parents, Staff | Booking and scheduling |
| `document_hub` | All users | Document sharing and access |
| `letter_templates` | Staff | Template-based correspondence |
| `sms_email` | Staff to Parents/Students | Outbound SMS and email |
| `activity_feed` | All users | Chronological activity stream |
| `forums` | Staff, Students | Discussion threads |


## Internal Messaging

The messaging module (`MessageService`) provides secure, internal user-to-user messaging within the college system.

### Sending a Message

1. Open the Messaging section from the sidebar.
2. Click "New Message" or "Compose".
3. Select a recipient from the user picker. All active users (staff and students) are listed with their display names and roles.
4. Enter a subject line (required) and message body.
5. Click Send.

Messages cannot be sent to yourself. Both sender and recipient must be active users.

### Inbox and Sent Items

The messaging interface provides two views:

| View | Description |
|------|-------------|
| Inbox | Messages received, ordered by date (newest first). Filter by unread only. |
| Sent | Messages you have sent, ordered by date (newest first). |

The inbox displays the sender's display name (resolved from staff or student records, falling back to username). Up to 50 messages are shown by default.

### Reading and Managing Messages

- Opening a message automatically marks it as read if you are the recipient.
- You can manually mark messages as read using the Mark Read action.
- The unread count badge updates in real time across the interface.
- Deleting a message performs a soft delete -- it removes the message from your view without affecting the other party's copy.

### Key Service Methods

| Method | Purpose |
|--------|---------|
| `send_message` | Send a message to another user |
| `get_inbox` | Retrieve received messages, optionally unread only |
| `get_sent` | Retrieve sent messages |
| `get_message` | View a single message (auto-marks as read) |
| `mark_read` | Manually mark a message as read |
| `count_unread` | Get the unread message count for badge display |
| `delete_message` | Soft-delete a message for the current user |
| `get_all_users` | List all active users for the recipient picker |


## Notifications

The notification module (`NotificationService`) delivers system-generated alerts to users. Unlike messages, notifications are one-directional and typically triggered by system events.

### Notification Types

| Type | Use Case |
|------|----------|
| `info` | General information (e.g., timetable change) |
| `success` | Confirmation of completed actions (e.g., enrolment confirmed) |
| `warning` | Items requiring attention (e.g., low attendance alert) |
| `alert` | Urgent items (e.g., safeguarding concern raised) |

### Sending Notifications

Notifications can be sent individually or in bulk:

- **Individual**: Target a single user with a specific notification.
- **Bulk**: Send the same notification to multiple users at once (e.g., all students on a course).

Each notification requires a title. The message body and type are optional (defaults to `info`).

### Managing Notifications

- View all notifications or filter to unread only (up to 50 by default).
- Mark individual notifications as read, or use "Mark All Read" to clear the badge.
- Old notifications are automatically cleaned up after 30 days using the `delete_old` method.


## Announcements

The announcements module (`AnnouncementService`) supports college-wide or targeted broadcast communication.

### Creating an Announcement

1. Navigate to the Announcements section.
2. Click "New Announcement".
3. Fill in the required fields:
   - **Title** -- A concise headline.
   - **Content** -- The full announcement text.
   - **Author** -- Automatically set to the logged-in user.
4. Optionally configure:
   - **Category** -- Classify the announcement (e.g., academic, pastoral, facilities).
   - **Target Role** -- Restrict visibility to specific roles (e.g., students only, staff only).
   - **Pinned** -- Pin important announcements to the top of the list.
   - **Publish Date** -- Schedule for future publication.
   - **Expiry Date** -- Automatically remove after a specified date.
   - **Status** -- Set as draft or published.

### Managing Announcements

- List announcements with filters by category, status, or target role.
- Update announcement content, category, or scheduling after creation.
- Delete announcements that are no longer relevant.
- Use the count function to monitor announcement volume by category or status.


## Parent Portal

The parent portal (`ParentService`) gives parents and carers secure access to their child's college information.

### Linking Parents to Students

Before parents can access data, an administrator must create a parent-student link:

1. Go to the Parent Portal administration section.
2. Select the parent user account and the student record.
3. Specify the relationship (e.g., parent, guardian, carer).
4. Save the link.

Parents can be linked to multiple students, and students can have multiple linked parents.

### Available Parent Views

Once linked, parents can view the following information for each of their children:

| View | Data Shown |
|------|------------|
| Grades | All grades across enrolled courses, including course code and title |
| Attendance | Per-course attendance summary: total sessions, present, late, absent, excused, and percentage rate |
| Timetable | Weekly timetable showing all enrolled courses with day, time, and room details |

### Data Security

- All parent data access is verified against the parent-student link before any data is returned.
- Parents can only see data for students they are formally linked to.
- Links can be removed by administrators at any time.


## Parents' Evening

The parents' evening module (`ParentsEveningService`) manages the scheduling and booking of parents' evening appointments.

### Setting Up a Parents' Evening

1. Create a new evening event with a title, date, start/end times, and slot duration (default 5 minutes).
2. Generate time slots for each teacher who will be available.
3. Publish the evening so parents can begin booking.

### Booking Workflow

1. Parents view available slots for each teacher.
2. Parents select and book a slot, linking it to their child.
3. The slot status changes from "available" to "booked".
4. Parents can view all their bookings for a given evening.
5. Slots can be cancelled by staff if needed, returning them to available status.

### Managing Evenings

| Action | Description |
|--------|-------------|
| Create evening | Set up a new event with date, time, and slot configuration |
| List evenings | View all evenings, optionally filtered by status |
| Update evening | Modify title, date, times, or status |
| Create slots | Add time slots for specific teachers |
| List slots | View all slots for an evening, optionally for a specific teacher |
| Book slot | Parent books a slot for their child |
| Cancel slot | Staff cancels a booking, freeing the slot |


## Document Hub

The document hub module provides centralised document sharing across the college. Staff can upload and categorise documents for access by specific user groups.

### Document Categories

Documents can be organised by type, such as policies, procedures, forms, templates, curriculum resources, and general information. Access can be restricted by role to ensure sensitive documents are only visible to authorised users.


## Letter Templates

The letter templates module enables staff to create and manage reusable letter templates for standard college correspondence.

### Common Template Types

- Offer letters and enrolment confirmations.
- Attendance concern letters (first, second, and final warning stages).
- Achievement and commendation letters.
- Disciplinary outcome letters.
- Reference requests and responses.

Templates support merge fields that are populated automatically from student and course records when a letter is generated.


## SMS and Email Integration

The SMS/email module (`sms_email`) provides outbound communication to parents and students via external channels.

### Sending Communications

1. Select the communication type (SMS or email).
2. Choose recipients individually, by course group, or by tutor group.
3. Compose the message or select a pre-defined template.
4. Review and send.

### Use Cases

- Absence notifications to parents.
- Event reminders and invitations.
- Emergency communications.
- Application status updates.


## Activity Feed

The activity feed module provides a chronological stream of significant events across the college system. It aggregates activity from multiple modules into a single, filterable timeline.

### Feed Content

The activity feed may include entries such as:

- New announcements published.
- Assignment deadlines approaching.
- Attendance alerts triggered.
- Grade updates recorded.
- System maintenance notifications.


## Forums

The forums module provides discussion board functionality for staff and students.

### Forum Features

- Create discussion topics organised by category or course.
- Post replies and engage in threaded conversations.
- Moderate content with staff oversight.
- Pin important topics to the top of the forum list.

Forums are particularly useful for course-specific discussions, student council communications, and cross-college consultation on policies or events.


## Cross-System Messaging

Staff often need to message colleagues in another education system — for
example a college tutor talking to a Year 11 form tutor at the feeder
secondary school about a transitioning student. This is handled by the
**Cross-System Messaging** feature, embedded directly into the College
SMS & Email screen and the College CLI's SMS/Email menu so you don't
need to leave email to talk to staff in University, Secondary, or Primary.

### Where to find it

| Interface | Location |
|-----------|----------|
| GUI | **Communication → SMS & Email**, then the **Cross-System Email** tab |
| CLI | **Communication → SMS & Email**, option `6) Cross-System Messages` |

### What it does

| Tab / option | Purpose |
|---|---|
| Inbox | Messages other systems' staff have sent to you. Shows sender name, system, subject, related student, date, and read state. |
| Sent | Messages you've sent out to other systems. |
| Compose | Pick a target system (Primary / Secondary / College / University), then a recipient from that system's staff list, optionally tag a student name, then enter subject + body. |

Messages are stored centrally in `auth.db` (`cross_system_messages`
table) so the same message is visible from whichever system the
recipient logs into.

### Service reference

| Method | Purpose |
|--------|---------|
| `InterSystemMessagingService.send_message` | Send a message to a staff member in another system |
| `InterSystemMessagingService.get_inbox` | Retrieve messages received from other systems |
| `InterSystemMessagingService.get_sent` | Retrieve messages sent to other systems |
| `InterSystemMessagingService.get_staff_list(system)` | List staff in a target system for the recipient picker |
| `InterSystemMessagingService.mark_read` | Mark an inter-system message as read |
| `InterSystemMessagingService.search_messages` | Search inbox + sent by subject, body, or student name |

The CLI counterpart lives in
`education_system.shared.messaging.cross_system_cli` and the reusable
GUI panel in `education_system.shared.messaging.cross_system_panel`.


## Idle / inactivity auto-logout

The College GUI and CLI both auto-log-out after **30 minutes of inactivity**
to reduce the risk of an unattended terminal exposing student data.

| Interface | How activity is tracked |
|-----------|-------------------------|
| GUI | Mouse motion, key presses, mouse buttons, and scroll-wheel events on the main window (via `bind_all`) reset the idle timer. |
| CLI | The menu prompt (`get_choice`) is wrapped in a `SIGALRM` watchdog. Any input — even pressing Enter at a menu — resets the timer. Long-running actions inside menu handlers (e.g. typing a long message body) are not bounded by the timeout; the clock starts again the next time you return to a menu prompt. |

When the timeout fires:

- **GUI:** A `Session Expired` dialog appears, then the application calls `auth.logout()`, requests the unified login screen via `request_logout()`, and destroys the window.
- **CLI:** The terminal prints `⚠ Logged out after 30 minutes of inactivity.`, calls `auth.logout()`, and exits the process cleanly.

The default of 30 minutes is set inside `CollegeApp.__init__` (GUI) and
the College `cli_main.main()` (CLI). To change it, look for the
`attach_idle_timeout(self, ..., timeout_minutes=30)` call in
`college_system/modules/shared/gui/main_gui.py` or the
`enable_idle_timeout(30, ...)` call in
`college_system/modules/shared/cli/cli_main.py`. The CLI auto-logout
is a no-op on platforms without `signal.SIGALRM` (e.g. Windows).

See `docs/sixth_form/security/SESSION_TIMEOUT.md` for the full
configuration and security rationale.


## Best Practices

- Use announcements for broadcast information and messaging for individual communication.
- Set expiry dates on time-sensitive announcements to keep the feed current.
- Encourage parents to check the parent portal regularly by linking it to parents' evening bookings.
- Use notification types consistently so users can quickly identify the urgency of alerts.
- Review and archive old letter templates annually to ensure accuracy.
- Use cross-system messaging to coordinate transitions and shared-student conversations with feeder/sender schools — keep one-off conversations there rather than spreading them across email and phone.
- Don't disable the idle-timeout watchdog on shared/lab machines; lower it if you handle particularly sensitive records.
