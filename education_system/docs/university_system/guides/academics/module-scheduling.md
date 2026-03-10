# Module Scheduling & Timetabling Guide

This guide covers class scheduling, timetable generation, room and instructor management, conflict detection, and reporting within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Room Management](#room-management)
- [Instructor Management](#instructor-management)
- [Creating Schedules](#creating-schedules)
- [Timetable Generation](#timetable-generation)
- [Conflict Detection & Resolution](#conflict-detection--resolution)
- [Analytics & Reporting](#analytics--reporting)
- [Import & Export](#import--export)
- [Templates](#templates)
- [Holiday Management](#holiday-management)
- [Settings](#settings)
- [Data Management](#data-management)

## Overview

The Module Scheduling system manages class timetables across the institution. It handles room allocation, instructor assignment, conflict detection, and timetable generation with support for multiple export formats.

**Key files:**
- Service: `modules/domain/academics/services/module_scheduling.py`
- GUI: `modules/domain/academics/gui/module_scheduling/`
- Core class: `ModuleScheduler`

### Scheduling Constants

```
Days: Monday, Tuesday, Wednesday, Thursday, Friday
Time Slots: 09:00 - 17:00 (hourly)
Session Types: Lecture, Lab, Tutorial, Seminar, Workshop
Room Types: Lecture Hall, Lab, Tutorial Room, Seminar Room, Workshop Room, Computer Lab, Other
```

## Getting Started

### CLI Access

From the main menu, select **Module Scheduling**. The CLI provides 29 options organized into:
- Analytics & Reporting (options 1-5)
- Advanced Scheduling (options 6-11)
- Conflict Management (options 12-14)
- Calendar & Exports (options 15-17)
- Data Management (options 18-21)
- Basic Operations (options 22-26)
- Notifications & Holidays (options 27-28)

### GUI Access

The GUI provides 9 main tabs:

| Tab | Purpose |
|-----|---------|
| Dashboard | System statistics and activity log |
| Schedules | Create, edit, and delete schedules |
| Rooms | Room management and utilization |
| Instructors | Faculty management and workload |
| Timetables | Generate and export timetables |
| Analytics | Reports and data analysis |
| Conflicts | Detect and resolve conflicts |
| Management | Backups, validation, data repair |
| Settings | System configuration and holidays |

## Room Management

### Adding a Room

1. Navigate to the **Rooms** tab
2. Click **Add Room**
3. Enter room details:
   - **Room Number** (e.g., "A101")
   - **Building** (e.g., "Science Building")
   - **Capacity** (number of seats)
   - **Room Type**: Lecture Hall, Lab, Tutorial Room, etc.
   - **Equipment**: Projector, whiteboard, computers, etc.
   - **Accessibility Compliant**: Yes/No
4. Save the room

### Viewing Room Utilization

The room list shows each room's current utilization rate based on scheduled sessions. Click a room to see its full weekly schedule.

### Finding Free Rooms

Use the **Find Free Rooms** feature (CLI option 10) to search for available rooms at a specific day and time, filtered by capacity and type requirements.

## Instructor Management

### Adding an Instructor

1. Navigate to the **Instructors** tab
2. Click **Add Instructor**
3. Enter instructor details:
   - Name and email
   - Department and specialization
   - **Max Courses Per Semester**
   - **Max Hours Per Week**
   - **Preferred Days** (e.g., Monday, Wednesday, Friday)
   - **Preferred Times** (e.g., 09:00-13:00)
4. Save the instructor profile

### Workload Tracking

The system monitors instructor workload against their configured limits. The instructors view shows:
- Current course count vs. maximum
- Weekly hours assigned vs. maximum
- Preference alignment (how well their schedule matches preferences)

## Creating Schedules

### Manual Schedule Creation

1. Navigate to the **Schedules** tab
2. Click **Add Schedule**
3. Select:
   - **Module Code** (from available modules)
   - **Day of Week**
   - **Start Time** and **End Time**
   - **Room** (from available rooms)
   - **Instructor** (from available instructors)
   - **Session Type**: Lecture, Lab, Tutorial, Seminar, Workshop
4. The system automatically checks for conflicts before saving
5. If conflicts are found, alternative slots are suggested

### Smart Scheduling Assistant

The scheduling wizard (CLI option 6) guides you through schedule creation:

1. Select a module
2. The system analyzes instructor availability and room capacity
3. Optimal time slots are suggested based on:
   - Room availability
   - Instructor preferences and workload
   - Existing schedule patterns
   - Conflict avoidance
4. Confirm the suggestion or modify manually

### Batch Import

Import multiple schedules from a CSV file (CLI option 7 or File menu):

```csv
module_code,day_of_week,start_time,end_time,room_id,instructor_id,session_type
CS101,Monday,09:00,10:00,1,1,Lecture
CS101,Wednesday,14:00,16:00,5,1,Lab
```

## Timetable Generation

### Student Timetables

1. Navigate to the **Timetables** tab
2. Enter a Student ID
3. Click **Generate Student Timetable**
4. The system queries enrollment data and displays a visual grid timetable
5. Export or email the timetable

### Instructor Timetables

1. Enter an Instructor ID
2. Click **Generate Instructor Timetable**
3. View the instructor's complete weekly schedule

### Export Formats

| Format | Description |
|--------|-------------|
| PDF | Visual formatted timetable |
| CSV | Spreadsheet-compatible data |
| Excel | Formatted Excel workbook |
| iCal | Calendar file (.ics) for import into calendar apps |

### Email Timetables

Timetables can be emailed directly to students or instructors from the Timetables tab.

## Conflict Detection & Resolution

### Types of Conflicts

| Conflict Type | Description |
|--------------|-------------|
| Room Double-Booking | Same room scheduled for overlapping time slots |
| Instructor Conflict | Same instructor assigned to overlapping sessions |
| Student Conflict | Student enrolled in modules with overlapping schedules |

### Detecting Conflicts

1. Navigate to the **Conflicts** tab
2. Click **Detect All Conflicts**
3. The system scans all schedules and identifies overlaps
4. Results show conflict type, affected entities, and details

### Resolving Conflicts

1. Select a conflict from the list
2. Review the affected schedules
3. Options:
   - Modify one of the conflicting schedules
   - Use **Find Alternative Slots** for suggestions
   - Add resolution notes
4. Mark the conflict as resolved
5. The resolution is tracked in the `schedule_conflicts` table

## Analytics & Reporting

### Available Analytics

| Report | Description |
|--------|-------------|
| Room Utilization | Usage rates per room, building, or time slot |
| Instructor Workload | Hours and courses per instructor |
| Peak Usage Analysis | Busiest time slots and days |
| Visual Charts | Matplotlib-generated charts and graphs |

### Generating Reports

1. Navigate to the **Analytics** tab
2. Select the analysis type
3. View results as text summaries or visual charts
4. Export to PDF for distribution

### CLI Analytics

- **Option 1**: Room Utilization Report
- **Option 2**: Workload Report
- **Option 3**: Analytics Dashboard
- **Option 4**: Visual Timetables
- **Option 5**: Utilization Charts

## Import & Export

### CSV Export

Export all schedules to CSV (CLI option 16 or File menu):
- Includes all schedule fields
- Can be opened in any spreadsheet application

### iCal Export

Export schedules as iCalendar files (CLI option 15):
- Compatible with Google Calendar, Outlook, Apple Calendar
- Includes event details, location, and instructor

### PDF Reports

Generate formatted PDF reports (CLI option 17):
- Professional layout with institutional branding
- Includes room schedules, instructor timetables, and summaries

## Templates

Save and reuse scheduling patterns:

### Saving a Template

1. Create a schedule configuration
2. Choose **Schedule Templates** (CLI option 8)
3. Name the template and add a description
4. The template stores the complete scheduling pattern

### Loading a Template

1. Select from saved templates
2. Apply to a new semester or term
3. Adjust individual schedules as needed

## Holiday Management

### Adding Holidays

1. Navigate to **Settings** > **Holiday Management** (or CLI option 28)
2. Add a holiday:
   - Holiday name
   - Start and end dates
   - Description
   - Recurring (yes/no for annual events)

### Holiday Conflict Checking

The system checks for scheduling conflicts with holidays:
- Warns when creating schedules that fall on holidays
- Reports which existing schedules overlap with holidays

## Settings

### System Settings

Configure via the **Settings** tab or CLI option 21:

| Setting | Description |
|---------|-------------|
| Institution Name | Your institution's name |
| Semester Start/End | Current semester date range |
| Default Session Duration | Duration in minutes for new sessions |
| Email Notifications | Enable/disable schedule change emails |
| Auto Backup | Enable/disable automatic database backups |

Settings are stored in the `scheduling_system_settings` table.

## Data Management

### Backups

1. Navigate to the **Management** tab
2. Click **Create Backup**
3. Enter a name and description for the backup
4. The system saves a complete snapshot of all scheduling data

### Restoring

1. Click **Restore Backup**
2. Select from available backups (listed with date and size)
3. Confirm the restoration

### Data Validation

Run validation checks to ensure data integrity:
- **Validate Data**: Check for orphaned records and invalid references
- **Clean Orphaned Records**: Remove records with broken relationships
- **Repair Issues**: Auto-fix common data problems

### Notifications

The system tracks notifications in the `notifications` table. Schedule change emails are sent automatically when:
- A room assignment changes
- A session time is modified
- A session is cancelled

## Permissions

| Feature | Admin | Staff/Instructor | Student |
|---------|-------|-------------------|---------|
| Manage rooms | Full | Full | No access |
| Manage instructors | Full | Full | No access |
| Create/edit schedules | Full | Full | No access |
| View timetables | Full | Own + students | Own only |
| Generate reports | Full | Full | No access |
| Resolve conflicts | Full | Full | No access |
| System settings | Full | No access | No access |
| Backup/restore | Full | No access | No access |
