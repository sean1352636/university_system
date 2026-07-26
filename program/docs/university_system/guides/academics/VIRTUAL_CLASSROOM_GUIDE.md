# Virtual Classroom System - User Guide

## Overview

The Virtual Classroom System provides real-time online collaboration features for instructors and students, including video conferencing integration, breakout rooms, live polls, chat functionality, and screen sharing capabilities.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Main Features](#main-features)
3. [Classroom Management](#classroom-management)
4. [Breakout Rooms](#breakout-rooms)
5. [Live Polls](#live-polls)
6. [Chat & Communication](#chat--communication)
7. [Recording Management](#recording-management)
8. [Analytics & Reporting](#analytics--reporting)
9. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Accessing Virtual Classroom

**From GUI:**
1. Launch the main GUI application
2. Navigate to **Academics** → **Virtual Classroom**
3. Login with your credentials (Instructor or Student role)

**Permissions Required:**
- **Instructors**: Create/manage classrooms, control breakout rooms, create polls
- **Students**: Join classrooms, participate in breakout rooms, respond to polls

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
   - **Enable Chat**: Allow student messaging
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

## Breakout Rooms

### Creating Breakout Rooms

Breakout rooms allow small group discussions and activities.

**Setup:**
1. During active session, click **Breakout Rooms**
2. Choose creation method:
   - **Automatic Assignment**: System distributes students evenly
   - **Manual Assignment**: Drag students to specific rooms
   - **Self-Select**: Students choose their own room
3. Configure settings:
   - **Number of Rooms**: 2-20 rooms
   - **Duration**: Auto-close after X minutes
   - **Allow Return**: Students can switch rooms
4. Click **Create Rooms**

**Managing Active Breakout Rooms:**
- **Broadcast Message**: Send announcement to all rooms
- **Join Room**: Enter a specific room to observe/assist
- **Close Rooms**: Return all students to main session
- **Extend Time**: Add more time to breakout session

**Student Experience:**
- Automatically moved to assigned room
- Can see room members and communicate
- Return to main room when time expires or instructor closes

---

## Live Polls

### Creating a Poll

Engage students with real-time polls and quizzes.

**Steps:**
1. Click **Create Poll** during active session
2. Enter poll details:
   - **Question**: The poll question
   - **Type**: Multiple choice, True/False, Free text, Rating scale
   - **Options**: Answer choices (for multiple choice)
   - **Anonymous**: Hide respondent names
   - **Correct Answer**: (Optional) For quiz-style polls
3. Click **Launch Poll**

**Poll Types:**

| Type | Description | Use Case |
|------|-------------|----------|
| Multiple Choice | Select one or many options | Knowledge checks, opinions |
| True/False | Binary choice | Quick comprehension checks |
| Free Text | Open-ended response | Reflections, questions |
| Rating Scale | 1-5 or 1-10 rating | Satisfaction, agreement level |
| Word Cloud | Students submit words | Brainstorming, associations |

**Viewing Results:**
- **Live Results**: See responses in real-time
- **Export**: Download results as CSV/PDF
- **Display to Class**: Show aggregate results (bar chart, pie chart)
- **Correct Answers**: Reveal correct answer with explanation

**Analytics:**
- Response rate percentage
- Time to respond (average)
- Most common answers
- Individual student responses (non-anonymous)

---

## Chat & Communication

### Chat Features

**Main Classroom Chat:**
- **Public Messages**: Visible to all participants
- **Private Messages**: Direct message to instructor or student
- **File Sharing**: Share documents, images (max 10MB)
- **Emoji Reactions**: React to messages
- **Message Search**: Find previous messages

**Chat Moderation (Instructor):**
- **Mute Chat**: Disable student messaging
- **Delete Messages**: Remove inappropriate content
- **Slow Mode**: Limit message frequency (1 per X seconds)
- **Chat Archive**: Save chat transcript

**Hand Raise Feature:**
- Students click **Raise Hand** to signal question
- Instructor sees queue and can call on students
- Lower hand automatically after being called on

**Announcements:**
- Instructor can send highlighted announcements
- Appears prominently for all participants
- Persists until dismissed

---

## Recording Management

### Recording Sessions

**Starting a Recording:**
1. Click **Start Recording** in classroom controls
2. All participants notified that recording is in progress
3. Records video, audio, chat, and screen shares

**Recording Settings:**
- **Record Breakout Rooms**: Include or exclude breakout discussions
- **Record Chat**: Include chat transcript
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
- Recordings stored in: `data/virtual_classroom/recordings/`
- File naming: `{classroom_id}_{date}_{time}.mp4`
- Retention policy: Auto-delete after 90 days (configurable)

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
- **Chat Activity**: Messages sent per student
- **Poll Response Rate**: % who responded to polls
- **Hand Raises**: Questions asked per student
- **Breakout Room Activity**: Time in breakouts, interactions

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
   - **Poll Results**: All poll data
   - **Chat Transcript**: Full conversation log
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
4. Check logs: `logs/virtual_classroom.log`

**Problem: "Breakout Rooms Not Working"**

**Solutions:**
1. Ensure minimum 2 students in session
2. Check if rooms are already active
3. Verify instructor permissions
4. Close existing rooms before creating new ones

**Problem: "Chat Messages Not Sending"**

**Solutions:**
1. Check if chat is muted by instructor
2. Verify internet connection
3. Ensure message meets length limit (500 chars)
4. Refresh session

### Performance Optimization

**For Large Classes (50+ participants):**
- Disable video for students (audio only)
- Use gallery view sparingly
- Limit screen sharing to instructor
- Disable chat reactions/emojis
- Use polls instead of open chat for Q&A

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
   - Prepare polls and breakout room assignments
   - Have backup plan for technical issues

2. **During Session:**
   - Start recording if needed
   - Use polls every 10-15 minutes to maintain engagement
   - Monitor chat and hand raises regularly
   - Provide clear instructions for breakout rooms
   - Take breaks for long sessions (every 45-60 minutes)

3. **Post-Session:**
   - End session properly (don't just close window)
   - Review chat transcript for questions
   - Generate attendance report
   - Share recording link within 24 hours

### For Students

1. **Join on time** - Log in 2-3 minutes early
2. **Test equipment** - Verify audio/video works
3. **Minimize distractions** - Close unnecessary applications
4. **Participate actively** - Respond to polls, use chat appropriately
5. **Use hand raise** - Don't interrupt with audio
6. **Be respectful** - Professional behavior in chat and discussions

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Mute/Unmute | Ctrl + D |
| Start/Stop Video | Ctrl + E |
| Raise Hand | Alt + Y |
| Open Chat | Ctrl + Shift + C |
| Share Screen | Ctrl + Shift + S |
| Leave Session | Ctrl + Shift + Q |
| Toggle Full Screen | F11 |

---

## API Integration

### Embedding Virtual Classroom

External applications can integrate virtual classroom functionality:

```python
from university_system.modules.domain.academics.services.virtual_classroom import VirtualClassroomManager

# Create manager instance
vcm = VirtualClassroomManager()

# Create classroom programmatically
classroom_id = vcm.create_classroom(
    name="API Test Classroom",
    instructor_id="INST001",
    course_code="CS101",
    max_participants=50,
    enable_recording=True
)

# Generate join link for students
join_link = vcm.get_join_link(classroom_id, student_id="STU001")

# Start recording
vcm.start_recording(classroom_id)
```

### Webhooks

Configure webhooks to receive real-time events:

**Available Events:**
- `classroom.created`
- `classroom.started`
- `classroom.ended`
- `participant.joined`
- `participant.left`
- `poll.created`
- `poll.completed`
- `recording.ready`

---

## Additional Resources

- **Video Tutorials**: `docs/videos/virtual_classroom_tutorial.mp4`
- **FAQs**: `docs/faqs/virtual_classroom_faq.md`
- **Technical Support**: helpdesk@university.edu
- **Feature Requests**: Submit via Student Support portal

---

## Version History

- **v5.0.0** (2025-01): Current version with full feature set
- **v4.5.0** (2024-12): Added breakout room analytics
- **v4.0.0** (2024-10): Introduced recording trimming feature
- **v3.5.0** (2024-08): Enhanced poll types (word cloud, rating)

---

**Last Updated**: January 2026
**Module**: `university_system/modules/domain/academics/services/virtual_classroom/`
**Support**: Contact IT Support via Helpdesk system
