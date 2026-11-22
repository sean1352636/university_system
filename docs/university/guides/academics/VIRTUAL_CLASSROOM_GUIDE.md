# Virtual Classroom System - User Guide

## Overview

The Virtual Classroom System provides real-time online collaboration features for instructors and students, including video conferencing integration, session scheduling, participant and attendance tracking, and recording management. The meeting itself runs on Zoom, Teams or Google Meet, which provide chat, polls and breakout rooms natively, so this system does not reproduce them.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Main Features](#main-features)
3. [Classroom Management](#classroom-management)
4. [Recording Management](#recording-management)
5. [Analytics & Reporting](#analytics--reporting)
6. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Accessing Virtual Classroom

**From GUI:**
1. Launch the main GUI application
2. Navigate to **Academics** → **Virtual Classroom**
3. Login with your credentials (Instructor or Student role)

**Permissions Required:**
- **Instructors**: Create/manage classrooms and sessions
- **Students**: Join classrooms

### System Requirements

- Python 3.8+
- Stable internet connection
- Audio/video hardware (for conferencing features)
- Screen resolution: 1024x768 minimum (1920x1080 recommended)

---

## Main Features

### Creating a Virtual Classroom (Instructors Only)

1. Click **Create Classroom** button
2. Fill in classroom details:
   - **Classroom Name**: Descriptive name (e.g., "CS101 - Week 5 Lecture")
   - **Course Code**: Associated course
   - **Description**: Session topic/agenda
   - **Start Time**: Scheduled start (or "Start Now")
   - **Duration**: Estimated session length
   - **Max Participants**: Capacity limit (default: 100)
3. Configure settings:
   - **Enable Recording**: Auto-record session
   - **Enable Screen Share**: Allow participant screen sharing
   - **Waiting Room**: Hold students until instructor admits
4. Click **Create**

### Joining a Classroom

**Students:**
1. View **Available Classrooms** list
2. Select your classroom
3. Click **Join**
4. Wait for instructor admission (if waiting room enabled)

**Direct Link:**
- Instructors can share a classroom link/code for quick access
- Enter code in **Join with Code** field

### Classroom Controls (Instructor)

**Participant Management:**
- **Admit/Remove Participants**: Control who's in the session
- **Mute/Unmute**: Manage audio permissions
- **Spotlight**: Highlight a specific student
- **Hand Raise Queue**: Manage student questions

**Session Controls:**
- **Start/Stop Recording**: Capture session for later review
- **Share Screen**: Present slides, documents, applications
- **Lock Room**: Prevent new participants from joining
- **End Session**: Close classroom for all participants

---

## Recording Management

### Recording Sessions

**Starting a Recording:**
1. Click **Start Recording** in classroom controls
2. All participants notified that recording is in progress
3. Records video, audio, and screen shares

**Recording Settings:**
- **Speaker View vs Gallery View**: Recording layout

**Managing Recordings:**
1. Navigate to **Recordings** tab
2. View list of past recordings with metadata:
   - Classroom name, date, duration
   - File size, format (MP4)
   - Processing status

**Recording Actions:**
- **Play**: Watch recording in browser
- **Download**: Save locally (MP4 format)
- **Share**: Generate shareable link (with permissions)
- **Trim**: Edit recording (remove intro/outro)
- **Delete**: Permanently remove recording

**Storage Management:**
- Recording metadata is kept in the `virtual_recordings` table; each row holds the recording's file URL
- Retention policy: Expires after 90 days (configurable)

---

## Analytics & Reporting

### Attendance Tracking

**Automatic Tracking:**
- System records join/leave timestamps
- Calculates total participation time
- Generates attendance reports

**View Attendance:**
1. Navigate to **Analytics** → **Attendance**
2. Select classroom and date range
3. View report showing:
   - Student name
   - Join time, leave time, total duration
   - Late arrivals, early departures
   - Participation rate percentage

**Export Options:**
- PDF attendance report
- CSV for spreadsheet analysis
- Integration with Attendance Tracker module

### Engagement Metrics

**Tracked Metrics:**
- **Participation Rate**: % of students who joined
- **Average Duration**: Mean session time per student
- **Hand Raises**: Questions asked per student

**Engagement Dashboard:**
- Visual charts showing participation trends
- Identify at-risk students (low engagement)
- Compare engagement across sessions
- Leaderboard (gamification, optional)

### Session Reports

**Generate Reports:**
1. Click **Generate Report** after session
2. Select report type:
   - **Session Summary**: Overview of session
   - **Detailed Attendance**: Individual participation
3. Choose format (PDF, HTML, CSV)
4. Download or email report

**Scheduled Reports:**
- Configure weekly/monthly summary reports
- Auto-email to instructors
- Include all sessions from period

---

## Troubleshooting

### Common Issues

**Problem: "Cannot Connect to Classroom"**

**Solutions:**
1. Check internet connection
2. Verify classroom is active (not ended)
3. Ensure you have permission to join
4. Try refreshing the classroom list
5. Contact instructor if in waiting room

**Problem: "Audio/Video Not Working"**

**Solutions:**
1. Check browser permissions (allow camera/mic)
2. Ensure no other application is using camera/mic
3. Try different browser (Chrome/Firefox recommended)
4. Restart browser
5. Check system audio/video settings

**Problem: "Recording Failed to Start"**

**Solutions:**
1. Check disk space (requires 1GB+ free)
2. Verify recording permissions (instructor only)
3. Ensure no other recording in progress
4. Check logs: `var/logs/university/app.log`

### Performance Optimization

**For Large Classes (50+ participants):**
- Disable video for students (audio only)
- Use gallery view sparingly
- Limit screen sharing to instructor

**Bandwidth Requirements:**
- Audio only: 50-100 Kbps
- Audio + Video (720p): 1.2-1.5 Mbps
- Screen share: 150-300 Kbps
- Recommended: 2+ Mbps download, 1+ Mbps upload

---

## Best Practices

### For Instructors

1. **Pre-Session:**
   - Create classroom 15 minutes early
   - Test audio/video before students join
   - Have backup plan for technical issues

2. **During Session:**
   - Start recording if needed
   - Monitor hand raises regularly
   - Take breaks for long sessions (every 45-60 minutes)

3. **Post-Session:**
   - End session properly (don't just close window)
   - Generate attendance report
   - Share recording link within 24 hours

### For Students

1. **Join on time** - Log in 2-3 minutes early
2. **Test equipment** - Verify audio/video works
3. **Minimize distractions** - Close unnecessary applications
4. **Participate actively** - Contribute to discussions
5. **Use hand raise** - Don't interrupt with audio
6. **Be respectful** - Professional behavior in discussions

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Mute/Unmute | Ctrl + D |
| Start/Stop Video | Ctrl + E |
| Raise Hand | Alt + Y |
| Share Screen | Ctrl + Shift + S |
| Leave Session | Ctrl + Shift + Q |
| Toggle Full Screen | F11 |

---

## API Integration

### Embedding Virtual Classroom

External applications can integrate virtual classroom functionality:

```python
from education_system.systems.university.domains.teaching.domain.virtual_classroom import VirtualClassroomManager

# Create manager instance
vcm = VirtualClassroomManager()

# Create classroom programmatically
classroom_id = vcm.create_classroom(
    session_name="API Test Classroom",
    instructor_id=1,
    platform="zoom",
    course_id=101,
    meeting_link="https://zoom.us/j/123456789",
    max_participants=50
)

# Read the join link back for students
join_link = vcm.get_classroom(classroom_id)["meeting_link"]
```

---

## Additional Resources

- **Technical Support**: helpdesk@university.edu
- **Feature Requests**: Submit via Student Support portal

---

## Version History

- **v5.0.0** (2025-01): Current version with full feature set
- **v4.0.0** (2024-10): Introduced recording trimming feature

---

**Last Updated**: January 2026
**Module**: `src/education_system/systems/university/domains/teaching/domain/virtual_classroom/`
**Support**: Contact IT Support via Helpdesk system
