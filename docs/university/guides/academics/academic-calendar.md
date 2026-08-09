# Academic Calendar Guide

This guide covers managing academic terms, events, deadlines, recurring events, and trip integration within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Academic Years & Semesters](#academic-years--semesters)
- [Event Management](#event-management)
- [Event Categories](#event-categories)
- [Recurring Events](#recurring-events)
- [Viewing the Calendar](#viewing-the-calendar)
- [Search & Filtering](#search--filtering)
- [Trip Integration](#trip-integration)
- [Exporting](#exporting)
- [Notifications](#notifications)
- [GUI Features](#gui-features)
- [Permissions](#permissions)

## Overview

The Academic Calendar module manages the institution's academic schedule, including terms, semesters, events, deadlines, and holidays. It integrates with the Trip Management module to coordinate educational excursions alongside the academic schedule.

**Key files:**
- Service: `modules/domain/academics/services/academic_calendar.py`
- GUI: `modules/domain/academics/gui/academic_calendar/`
- Core class: `AcademicCalendarManager`

## Getting Started

### CLI Access

From the main menu, select **Academic Calendar**. The menu is organized into sections based on your role:

**Calendar Management** (admin/staff):
- Add Event
- Update Event
- Delete Event
- View Calendar
- Export Calendar

**Trip Management** (if available):
- View All Trips
- Create New Trip
- Register for Trip
- View My Trip Registrations

**Integration** (admin):
- Create Calendar Event for Trip
- View Trip-Calendar Links

### GUI Access

The GUI provides a full-featured calendar interface with:
- Sidebar navigation
- Monthly/weekly/daily calendar views
- Event list view
- Drag-and-drop event management
- Color-coded event categories

## Academic Years & Semesters

### Managing Academic Years

Academic years define the overall timeframe for the institution:

1. Create an academic year (e.g., "2025-2026")
2. Set the start and end dates
3. Mark as active or inactive

### Managing Semesters

Each academic year contains semesters:

1. Select an academic year
2. Add semesters:
   - **Semester Name** (e.g., "Fall 2025", "Spring 2026")
   - **Start Date** and **End Date**
   - **Type**: Fall, Spring, Summer, Winter
3. Semesters link events to specific periods

### Database Tables

- `academic_years`: Year records with start/end dates and status
- `semesters`: Semester records linked to academic years

## Event Management

### Creating an Event

1. Select **Add Event** from the CLI menu, or click the add button in the GUI
2. Enter event details:
   - **Name** (required)
   - **Description**
   - **Event Type** (see categories below)
   - **Date** or **Date Range** (start and end)
   - **All Day**: Yes/No
   - **Location**
   - **Academic Year** (optional)
   - **Semester** (optional)
   - **Priority**: 1 (low) to 5 (high)
   - **Status**: Active, Cancelled, Postponed
3. Optionally set up recurrence rules
4. Save the event

### Updating an Event

1. Select **Update Event** or click on the event in the GUI
2. Modify any fields
3. Save changes
4. The `last_modified` timestamp updates automatically

### Deleting an Event

1. Select **Delete Event**
2. Choose the event to delete
3. Confirm the deletion
4. Associated notifications and links are cleaned up

### Event Fields

| Field | Description |
|-------|-------------|
| `name` | Event title (required) |
| `description` | Detailed description |
| `event_type` | Category (Academic, Holiday, etc.) |
| `date` / `date_start` / `date_end` | Single date or date range |
| `all_day` | Whether it spans the full day |
| `location` | Physical location |
| `academic_year_id` | Associated academic year |
| `semester_id` | Associated semester |
| `is_recurring` | Whether the event repeats |
| `recurrence_rule` | iCal-format recurrence rule |
| `status` | Active, Cancelled, Postponed |
| `priority` | 1-5 scale |

## Event Categories

The system includes 8 default event categories:

| Category | Icon | Color | Description |
|----------|------|-------|-------------|
| Academic | Books | Blue | Academic events and deadlines |
| Holiday | Party | Green | Holidays and breaks |
| Administrative | Clipboard | Orange | Administrative events |
| Social | Celebration | Pink | Social events and activities |
| Sports | Soccer | Purple | Sports and athletic events |
| Trip | Backpack | Cyan | Educational trips and excursions |
| Deadline | Clock | Red | Important deadlines |
| Meeting | Handshake | Brown | Meetings and conferences |

### Custom Categories

Administrators can create additional categories with:
- Custom name and description
- Color code (hex)
- Icon (emoji or text)

## Recurring Events

### Creating a Recurring Event

1. When adding or editing an event, enable **Recurring**
2. Set the recurrence rule:
   - **Frequency**: Daily, Weekly, Monthly, Yearly
   - **Interval**: Every N days/weeks/months
   - **End Date** or **Number of Occurrences**
   - **Days of Week** (for weekly): Select specific days
3. The system generates individual event instances based on the rule

### Managing Recurring Events

The GUI provides a dedicated recurring events dialog:
- View all recurring event patterns
- Edit the recurrence rule
- Delete individual instances or the entire series
- Preview generated dates before saving

### Recurrence Rules

Rules follow the iCal RRULE format internally:
```
FREQ=WEEKLY;BYDAY=MO,WE,FR;UNTIL=20260601
FREQ=MONTHLY;BYMONTHDAY=15;COUNT=12
```

## Viewing the Calendar

### CLI View

1. Select **View Calendar**
2. Optionally filter by:
   - Academic year
   - Semester
3. Events display in chronological order with:
   - Date and time
   - Event name and type
   - Location
   - Status

### GUI Views

The GUI offers multiple calendar views:

| View | Description |
|------|-------------|
| Month View | Full month grid with event indicators |
| Week View | Detailed weekly schedule |
| Day View | Hour-by-hour daily schedule |
| List View | Chronological event list |
| Events View | Filterable table of all events |

### Color Coding

Events are color-coded by category for visual distinction in all views.

## Search & Filtering

### Date Range Search

1. Select **Search Events**
2. Choose **Search by date range**
3. Enter start and end dates
4. Optionally filter by event type

### Advanced Search

Combine multiple criteria:
- **Text search**: Search in event names and descriptions
- **Date range**: Start and end dates
- **Event type**: Filter by category
- **Semester**: Filter by academic period
- **Status**: Active, Cancelled, Postponed

## Trip Integration

The calendar integrates with the Trip Management module to keep trips visible on the academic calendar.

### Creating Calendar Events for Trips

1. Select **Create Calendar Event for Trip** (admin only)
2. View available trips that don't yet have calendar events
3. Select a trip
4. Customize the event name and description (or use defaults)
5. The system creates a calendar event linked to the trip

### Viewing Trip-Calendar Links

1. Select **View Trip-Calendar Links**
2. See all trips with their associated calendar events
3. Links are maintained in the `trip_calendar_events` table

### Trip Menu Options

If Trip Management is available:
- **View All Trips**: Browse all educational trips
- **Create New Trip**: Set up a new trip (requires `create_trips` permission)
- **Register for Trip**: Sign up for a trip (requires `register_for_trips` permission)
- **View My Registrations**: See your trip registrations

## Exporting

### Export Formats

| Format | Description |
|--------|-------------|
| iCal (.ics) | Import into Google Calendar, Outlook, Apple Calendar |
| CSV | Spreadsheet-compatible data |
| PDF | Formatted calendar for printing |
| JSON | Machine-readable data export |

### Exporting the Calendar

1. Select **Export Calendar**
2. Choose the export format
3. Optionally filter by date range or category
4. Save the file

### iCal Export

The iCal export creates standard `.ics` files compatible with all major calendar applications. Events include:
- Title and description
- Start and end times
- Location
- Recurrence rules (for recurring events)

## Notifications

### Event Notifications

The system can send notifications for upcoming events:

1. Notifications are stored in the `event_notifications` table
2. Configure notification timing (e.g., 1 day before, 1 hour before)
3. Notification types: Email, SMS, In-app
4. Status tracking: Pending, Sent

### Setting Up Notifications

For individual events:
1. Edit the event
2. Add notification rules
3. Specify recipient and timing

For system-wide notifications:
- Configure default notification rules in settings
- Apply to all events of a specific type

## GUI Features

### Main GUI Components

The Academic Calendar GUI includes:

- **Sidebar**: Quick navigation to all sections
- **Calendar Grid**: Interactive monthly/weekly views
- **Event Details Panel**: Full event information
- **Quick Actions**: Fast event creation and management
- **Resource Management**: Room and resource booking
- **Report Generation**: Calendar analytics

### Dialogs

| Dialog | Purpose |
|--------|---------|
| Add/Edit Event | Create or modify events |
| Recurring Events | Manage recurrence patterns |
| Resources | View and allocate resources |
| Reports | Generate calendar reports |

### Keyboard Shortcuts

Common shortcuts are available for navigation and actions:
- Navigate between dates
- Quick event creation
- View switching
- Search activation

## Permissions

### Calendar Permissions

| Permission | Description |
|-----------|-------------|
| `manage_schedules` | Create, update, and delete events |
| `view_own_timetable` | View calendar and events |
| `export_data` | Export calendar data |
| `create_trips` | Create new trips |
| `view_trips` | View all trips |
| `register_for_trips` | Register for trips |
| `view_own_trip_registrations` | View personal trip registrations |

### Role Access

| Feature | Admin | Staff/Instructor | Student |
|---------|-------|-------------------|---------|
| Add/Edit/Delete events | Full | Full | No access |
| View calendar | Full | Full | Full |
| Export calendar | Full | Full | Full |
| Create trips | Full | Full | No access |
| Register for trips | No | No | Full |
| Trip-Calendar integration | Full | No access | No access |
| Manage categories | Full | No access | No access |

### Audit Trail

All calendar modifications are logged in the `calendar_audit_log` table:
- User ID and action
- Resource type and ID
- Old and new values
- Timestamp and IP address
