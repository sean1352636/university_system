# Attendance Tracking Guide

This guide covers attendance management, multiple check-in methods, reporting, notifications, and predictive analytics within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Recording Attendance](#recording-attendance)
- [QR Code Attendance](#qr-code-attendance)
- [Face Recognition](#face-recognition)
- [Geofencing](#geofencing)
- [Viewing Records](#viewing-records)
- [Reports & Analytics](#reports--analytics)
- [Predictive Analytics](#predictive-analytics)
- [Notifications & Alerts](#notifications--alerts)
- [Gamification](#gamification)
- [Settings & Configuration](#settings--configuration)
- [Backup & Recovery](#backup--recovery)

## Overview

The Attendance Tracking module provides enterprise-grade attendance management with multiple check-in methods (manual, QR code, face recognition, geofencing), automated notifications, predictive analytics, and comprehensive reporting.

**Key files:**
- Service: `modules/domain/academics/services/attendance/attendance_tracker.py`
- Notifications: `modules/domain/academics/services/attendance/attendance_notifications.py`
- GUI: `modules/domain/academics/gui/attendance_tracker/`

## Getting Started

### CLI Access

From the main menu, select **Attendance Tracking**. The CLI provides 25 options organized into sections:

1. **Attendance Management** (options 1-5): Recording and viewing
2. **Analytics & Reporting** (options 6-10): Reports and dashboards
3. **Gamification & Engagement** (options 11-13): Points and achievements
4. **Notifications & Alerts** (options 14-16): Alert configuration
5. **System Management** (options 17-20): Settings, backups, API, audit
6. **Integrations** (options 21-23): LMS, calendar, import/export

### GUI Access

The GUI provides a tabbed interface:

| Tab | Purpose |
|-----|---------|
| Dashboard | Statistics overview, trend charts, recent activity |
| Attendance | Record attendance using any method |
| Students | Student search and management |
| Reports | Generate and export reports |
| Analytics | Predictive analytics and gamification |
| Settings | System configuration |
| Admin | Diagnostics, audit logs, backups |

## Recording Attendance

### Manual Attendance

1. Select the module from the dropdown
2. Choose the date
3. Click **Manual Attendance**
4. Select a student from the enrolled list
5. Set status: **Present**, **Late**, **Absent**, or **Excused**
6. Add optional notes
7. Save the record

### Batch Attendance

Record attendance for multiple students at once:

1. Click **Batch Attendance**
2. Select the module and date
3. A list of all enrolled students appears
4. Set the status for each student
5. Submit all records at once

### Attendance Statuses

| Status | Description |
|--------|-------------|
| Present | Student attended the session |
| Late | Student arrived after the session started |
| Absent | Student did not attend |
| Excused | Absence with valid reason |

## QR Code Attendance

### Generating a QR Code

1. Select the module and date
2. Click **QR Attendance**
3. Set session details:
   - Start and end times
   - Location name
4. Click **Generate QR Code**
5. The QR code appears on screen with a configurable expiry (default: 15 minutes)

### Student Check-in

Students scan the displayed QR code with their mobile device. The system:
- Validates the QR code hasn't expired
- Records the timestamp, location, and IP address
- Marks the student as present
- Updates the attendance list in real-time

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `qr_code_expiry_minutes` | 15 | Time before QR code expires |

## Face Recognition

### Student Enrollment

Before face recognition can be used, students must be enrolled:

1. Open **Tools** > **Face Recognition Setup**
2. Select a student
3. Capture their photo using the camera
4. The system stores the face encoding in the `student_biometrics` table
5. Repeat for all students

### Taking Attendance

1. Click **Face Attendance** on the Attendance tab
2. The camera feed activates
3. The system detects faces in real-time
4. Recognized students appear with confidence scores
5. Successfully matched students are automatically marked as present
6. Unrecognized faces can be manually identified

### Requirements

Face recognition requires the following optional dependencies:
- `face_recognition` library
- `opencv-python` (cv2)
- A working webcam

## Geofencing

### Creating a Geofenced Session

1. Open **Tools** > **Geofencing Setup**
2. Select the module and date
3. Enter the location details:
   - Location name
   - GPS coordinates (latitude/longitude)
   - Radius in meters (default: 50m)
4. Create the session

### Student Check-in

Students check in via the attendance app with GPS enabled. The system:
- Calculates the distance between the student and the session location
- Marks present if within the geofence radius
- Records the exact distance for auditing

## Viewing Records

### Individual Records

View attendance for a specific student across all modules, showing:
- Date, time, and status for each session
- Check-in method used
- Overall attendance percentage

### Module Records

View attendance for an entire module, showing:
- All enrolled students and their attendance status per session
- Cohort-level statistics
- Session-by-session breakdown

## Reports & Analytics

### Available Reports

| Report | Description |
|--------|-------------|
| Student Attendance Report | Per-student detailed breakdown with percentages |
| Module Attendance Report | Cohort-level statistics and patterns |
| Executive Summary | Institution-wide attendance overview |
| At-Risk Student Report | Students below the attendance threshold |
| Trends Report | Attendance patterns over time |
| Custom Report | User-defined parameters and filters |
| Quick Report | Snapshot data for immediate review |

### Generating Reports

1. Navigate to the **Reports** tab
2. Select the report type
3. Set parameters (date range, module, student)
4. Click **Generate**
5. The report displays in a preview panel

### Exporting

Reports can be:
- Displayed in the GUI
- Exported to PDF
- Emailed directly to administrators
- Saved as CSV files

## Predictive Analytics

The system uses machine learning (Random Forest classifier) to predict at-risk students.

### Training the Model

1. Navigate to the **Analytics** tab
2. Click **Train Prediction Model**
3. The system extracts training data using these features:
   - Current attendance rate
   - Consecutive absences
   - Days since last attendance
   - Total sessions attended
   - Week of term
   - Day of week
   - Previous module performance
4. The model trains and displays performance metrics

### Predicting Risk

- **Single Prediction**: Select a student and module to get their risk score (0.0-1.0)
- **Batch Analysis**: Predict risk for all students in a module at once

Risk levels:
- **Low Risk**: Score < 0.3
- **Medium Risk**: Score 0.3 - 0.7
- **High Risk**: Score > 0.7

Results are stored in the `attendance_predictions` table.

## Notifications & Alerts

### Low Attendance Alerts

The system automatically monitors attendance rates and triggers alerts when students fall below the configured threshold.

1. Go to **Tools** > **Attendance Alerts**
2. Configure the threshold (default: 90%)
3. Set notification methods:
   - Email to student
   - Email to parent/guardian
   - SMS (if configured)
4. Alerts are created in the `attendance_alerts` table

### Parent Notifications

1. Open **Tools** > **Parent Notification System**
2. Search for a student
3. View parent contact information
4. Compose a notification message
5. Select delivery method (email or SMS)
6. Send immediately or schedule for later

### Alert Lifecycle

1. Alert created when threshold breached
2. Notification sent via configured channels
3. Student/parent can acknowledge the alert
4. Admin tracks acknowledgment status

## Gamification

The gamification system encourages attendance through engagement mechanics:

### Points System
- Students earn points for each attended session
- Points accumulate toward level progression

### Achievements & Badges
- Awarded for attendance milestones (e.g., 100% attendance for a week)
- Tracked in `user_achievements` table

### Leaderboards
- View top-attending students
- Filter by module or time period

### Streaks
- Track consecutive days of attendance
- Special recognition for long streaks

## Settings & Configuration

### Configurable Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `attendance_threshold_percentage` | 90% | Minimum attendance rate before alerts |
| `consecutive_absence_limit` | 3 | Max consecutive absences before alert |
| `qr_code_expiry_minutes` | 15 | QR code validity period |
| `enable_face_recognition` | false | Toggle face recognition feature |
| `enable_geofencing` | false | Toggle geofencing feature |
| `enable_qr_attendance` | true | Toggle QR attendance feature |
| `enable_predictive_analytics` | true | Toggle predictive analytics |
| `notification_enabled_students` | true | Send alerts to students |
| `notification_enabled_parents` | true | Send alerts to parents |

Settings are stored in the `attendance_settings` database table and can be modified from the **Settings** tab in the GUI or option 17 in the CLI.

### Attendance Policies

Create and manage attendance policies per module:
- Minimum attendance percentage
- Maximum consecutive absences
- Late tolerance minutes
- Makeup session allowance
- Auto-fail threshold
- Grace period days

## Backup & Recovery

### Creating Backups

1. Go to **Admin** > **Backup Database** (GUI) or option 18 (CLI)
2. The system creates a timestamped backup file
3. Backups are stored in the configured backup directory

### Scheduling Backups

Configure automatic backups from the backup settings:
- Set backup frequency
- Configure retention policy
- Enable automatic cleanup of old backups

### Restoring

1. Open the Backup Recovery interface
2. Select a backup from the list
3. Confirm the restoration
4. The system restores the database state and logs the recovery event
