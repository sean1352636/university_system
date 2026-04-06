# Lost & Found, Feedback System & Notifications Guide

This guide covers the Lost & Found item tracking, campus feedback/suggestion system, and the multi-channel notifications service within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Lost & Found](#lost--found)
  - [Reporting Lost Items](#reporting-lost-items)
  - [Reporting Found Items](#reporting-found-items)
  - [Automatic Matching](#automatic-matching)
  - [Claiming Items](#claiming-items)
  - [Item Photos](#item-photos)
  - [Statistics](#statistics)
- [Feedback System](#feedback-system)
  - [Submitting Feedback](#submitting-feedback)
  - [Voting & Trending](#voting--trending)
  - [Status Workflow](#status-workflow)
  - [Admin Responses](#admin-responses)
  - [Impact Tracking](#impact-tracking)
- [Notifications System](#notifications-system)
  - [Creating Notifications](#creating-notifications)
  - [Notification Channels](#notification-channels)
  - [Priority Levels](#priority-levels)
  - [User Preferences](#user-preferences)
  - [Daily Digest](#daily-digest)
  - [Smart Bundling](#smart-bundling)
  - [Quiet Hours](#quiet-hours)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

These three services provide essential campus life functionality: tracking lost and found items with automatic matching, a feedback and suggestion system with voting and status tracking, and a multi-channel notification service with smart bundling and quiet hours.

**Key files:**
- Lost & Found: `modules/domain/lost_found/services/lost_found_service.py`
- Feedback: `modules/domain/feedback/services/feedback_service.py`
- Notifications: `modules/domain/notifications/services/notifications_service.py`

---

## Lost & Found

### Reporting Lost Items

```python
from university_system.modules.domain.lost_found.services.lost_found_service import (
    LostFoundService
)

service = LostFoundService()

# Report a lost item
service.report_lost_item(
    reporter_id='S-12345',
    item_name='Blue Backpack',
    category='Bags',
    description='Navy blue JanSport backpack with laptop compartment',
    color='Blue',
    brand='JanSport',
    location_lost='Library - 2nd Floor',
    date_lost='2025-10-15',
    contact_info='john.doe@university.edu'
)
```

### Reporting Found Items

```python
service.report_found_item(
    reporter_id='S-67890',
    item_name='Blue Backpack',
    category='Bags',
    description='Blue backpack found near study area',
    color='Blue',
    brand='JanSport',
    location_found='Library - Study Area',
    date_found='2025-10-15',
    current_location='Library Front Desk'
)
```

### Item Status Values

**Lost Items:**

| Status | Description |
|--------|-------------|
| Active | Currently lost, actively searching |
| Found | Item has been located |
| Closed | Case resolved |

**Found Items:**

| Status | Description |
|--------|-------------|
| Available | Item is held and awaiting claim |
| Claimed | Item has been claimed by owner |
| Donated | Unclaimed item donated |
| Discarded | Item disposed of after retention period |

### Automatic Matching

When a lost or found item is reported, the system automatically searches for potential matches using a scoring algorithm:

```python
# Get potential matches for a lost item
matches = service.get_matches(item_id='lost_001', item_type='lost')
```

**Matching Algorithm:**

| Factor | Points | Description |
|--------|--------|-------------|
| Category | Required | Items must share the same category (0 if mismatch) |
| Item name | 30 | Similarity between item names |
| Color | 20 | Exact color match |
| Brand | 20 | Exact brand match |
| Location | 15 | Proximity of lost/found locations |
| Date | 10-15 | Closeness of lost/found dates |

**Minimum threshold: 50 points** for a match to be suggested.

### Claiming Items

#### Verification Questions

Admins can create verification questions for found items to validate ownership:

```python
# Create verification questions
service.create_verification_questions(
    item_id='found_001',
    questions=[
        'What is the laptop brand inside the backpack?',
        'How many zippers does the backpack have?',
        'Is there a keychain attached? If so, describe it.'
    ]
)
```

#### Submitting a Claim

```python
service.submit_claim(
    item_id='found_001',
    claimant_id='S-12345',
    answers={
        'q1': 'Dell XPS 15',
        'q2': 'Three zippers',
        'q3': 'Yes, a rubber duck keychain'
    },
    proof_of_ownership='I can show the purchase receipt for the backpack.'
)
```

#### Reviewing Claims

```python
# Admin reviews and approves/rejects claims
service.review_claim(
    claim_id='claim_001',
    status='approved',      # approved or rejected
    reviewer_id='admin_001',
    notes='Answers match item description. Identity verified.'
)
```

### Item Photos

```python
# Upload a photo (SHA-256 hash prevents duplicates)
service.add_item_photo(
    item_id='lost_001',
    item_type='lost',
    photo_path='/uploads/backpack_photo.jpg'
)

# Get item photos
photos = service.get_item_photos(item_id='lost_001', item_type='lost')

# Delete a photo
service.delete_item_photo(photo_id='photo_001')
```

Photo features:
- SHA-256 hash-based duplicate detection
- Associated with lost or found items
- Displayed in matching results

### Statistics

```python
# Overall system statistics
stats = service.get_statistics()
# Returns: total lost, total found, matched, claimed, recovery rate

# Breakdown by category
categories = service.get_category_breakdown()
# Returns: item count per category
```

### Lost & Found Database Schema

| Table | Purpose |
|-------|---------|
| `lost_items` | Lost item reports with details and status |
| `found_items` | Found item reports with current location |
| `item_photos` | Photos with SHA-256 hash deduplication |
| `item_matches` | Automatic matches between lost and found |
| `item_claims` | Claim submissions with verification answers |
| `verification_questions` | Security questions for ownership proof |

---

## Feedback System

### Submitting Feedback

```python
from university_system.modules.domain.feedback.services.feedback_service import (
    FeedbackService
)

service = FeedbackService()

# Submit feedback
service.submit_feedback(
    user_id='S-12345',
    category='Technology',
    title='WiFi connectivity in dormitories',
    description='The WiFi signal is consistently weak on the 3rd floor of North Hall.',
    priority='high',
    is_anonymous=False
)

# Submit a suggestion (convenience method)
service.submit_suggestion(
    user_id='S-12345',
    category='Campus Life',
    title='Extended library hours during finals',
    description='The library should stay open 24 hours during finals week.',
    is_anonymous=True
)
```

### Feedback Categories

| Category | Description |
|----------|-------------|
| Academic | Courses, teaching, curriculum |
| Housing | Dormitories, residence halls |
| Dining | Food services, meal plans |
| Technology | IT, WiFi, software, hardware |
| Campus Life | Events, activities, recreation |
| Safety | Security, lighting, emergency |
| Other | General feedback |

### Priority Levels

| Priority | Use Case |
|----------|----------|
| Low | Minor suggestions and observations |
| Normal | Standard feedback items |
| High | Issues affecting many students |
| Critical | Safety or urgent operational issues |

### Voting & Trending

Students can upvote suggestions to signal community interest:

```python
# Upvote a submission
service.upvote_submission(
    submission_id='sub_001',
    user_id='S-67890'
)
# One vote per user per submission (deduplication enforced)

# Remove a vote
service.remove_vote(
    submission_id='sub_001',
    user_id='S-67890'
)

# Get trending suggestions (highest vote count)
trending = service.get_trending_suggestions(limit=10)

# Get implemented suggestions
implemented = service.get_implemented_suggestions()
```

### Status Workflow

Feedback progresses through a defined workflow:

```
Submitted → Under Review → Planned → In Progress → Implemented
                  │
                  └──→ Declined
```

| Status | Description |
|--------|-------------|
| Submitted | New feedback awaiting review |
| Under Review | Being evaluated by staff |
| Planned | Approved and scheduled |
| In Progress | Actively being worked on |
| Implemented | Completed and deployed |
| Declined | Not approved (with reason) |

```python
# Update status (admin)
service.update_status(
    submission_id='sub_001',
    new_status='planned',
    updated_by='admin_001',
    notes='Scheduled for next semester facilities update.'
)
```

### Admin Responses

```python
# Add an official response
service.add_response(
    submission_id='sub_001',
    responder_id='admin_001',
    response='Thank you for your feedback. We are working with IT to install additional WiFi access points on the 3rd floor.'
)
```

### Impact Tracking

Track the impact of implemented suggestions:

```python
service.add_impact_data(
    submission_id='sub_001',
    users_affected=350,
    satisfaction_increase=15.5,   # Percentage
    cost_savings=0.0
)
```

### Searching Feedback

```python
# Full-text search
results = service.search_submissions(query='WiFi dormitory')

# Get submissions with filtering
filtered = service.get_submissions(
    category='Technology',
    status='under_review',
    priority='high'
)

# Get detailed submission with full history
details = service.get_submission_details(submission_id='sub_001')
```

### Feedback Statistics

```python
stats = service.get_statistics()
# Returns: total submissions, by category, by status, average response time,
#          implementation rate, top voted items
```

### Feedback Database Schema

| Table | Purpose |
|-------|---------|
| `feedback_submissions` | Main feedback/suggestion records |
| `feedback_categories` | Category definitions |
| `feedback_votes` | Upvote/downvote tracking |
| `feedback_responses` | Admin responses |
| `feedback_status_updates` | Status change history |
| `feedback_impacts` | Impact metrics for implemented items |
| `feedback_attachments` | File uploads |

---

## Notifications System

### Creating Notifications

```python
from university_system.modules.domain.notifications.services.notifications_service import (
    NotificationsService
)

service = NotificationsService()

# Create a notification
service.create_notification(
    user_id='S-12345',
    channel='Academic',
    title='Grade Posted',
    message='Your grade for CS101 Final Exam has been posted.',
    priority='medium',
    delivery_method='push'
)
```

### Notification Channels

| Channel | Examples |
|---------|----------|
| Academic | Grades, assignments, course updates |
| Social | Messages, friend requests, group invites |
| Financial | Payment due, aid disbursement, refund |
| Health | Appointments, health alerts, prescriptions |
| Housing | Maintenance, roommate requests, inspections |
| Events | Campus events, club meetings, deadlines |
| System | Account updates, security alerts, maintenance |

### Priority Levels

| Priority | Behavior |
|----------|----------|
| Low | Included in daily digest only |
| Medium | Standard notification delivery |
| High | Immediate delivery, bypasses digest |
| Urgent | Immediate delivery, bypasses quiet hours |

### Delivery Methods

| Method | Description |
|--------|-------------|
| Push | In-app push notification |
| Email | Email notification via email service |
| SMS | SMS message (high/urgent priority only) |

### Managing Notifications

```python
# Get notifications with filters
notifications = service.get_notifications(
    user_id='S-12345',
    channel='Academic',
    is_read=False
)

# Mark individual as read
service.mark_as_read(notification_id='notif_001')

# Mark all as read
service.mark_all_as_read(user_id='S-12345')

# Archive a notification
service.archive_notification(notification_id='notif_001')

# Delete old notifications (retention management)
service.delete_old_notifications(days=90)

# Get unread count
count = service.get_unread_count(user_id='S-12345')
```

### User Preferences

Configure notification delivery per channel:

```python
# Get current preferences
prefs = service.get_preferences(user_id='S-12345')

# Update preferences
service.update_preferences(
    user_id='S-12345',
    academic_enabled=True,
    social_enabled=True,
    financial_enabled=True,
    health_enabled=True,
    housing_enabled=True,
    events_enabled=False,     # Disable event notifications
    system_enabled=True
)
```

### Channel-Specific Settings

```python
# Get channel settings
settings = service.get_channel_settings(
    user_id='S-12345',
    channel='Academic'
)

# Update channel settings
service.update_channel_settings(
    user_id='S-12345',
    channel='Academic',
    enabled=True,
    min_priority='medium',     # Filter out low-priority
    delivery_method='push',
    bundle_enabled=True
)
```

### Daily Digest

Low-priority notifications are compiled into a daily digest:

```python
# Generate a daily digest for a user
digest = service.generate_daily_digest(user_id='S-12345')
# Compiles all unread low-priority notifications into a single summary
```

### Smart Bundling

Related notifications are automatically grouped:

```python
# Example: 5 assignment grade notifications bundled into one:
# "You have 5 new grade notifications for CS101, MATH201, ENG102..."
```

**Bundle settings:**
- Bundle time window: 300 seconds (5 minutes) default
- Notifications within the window and same channel are grouped
- Bundled notifications show a summary count

### Quiet Hours

Configure do-not-disturb periods:

```python
service.update_preferences(
    user_id='S-12345',
    quiet_hours_start='22:00',
    quiet_hours_end='08:00'
)
```

**Quiet hours behavior:**
- Low/Medium priority: Held until quiet hours end
- High priority: Held until quiet hours end
- Urgent priority: Delivered immediately (bypasses quiet hours)
- Supports midnight-spanning periods (e.g., 22:00-08:00)

### Notification Statistics

```python
stats = service.get_notification_stats(user_id='S-12345')
# Returns: total sent, read rate, channel breakdown,
#          average response time, preference summary
```

### Notifications Database Schema

| Table | Purpose |
|-------|---------|
| `notifications` | Core notification records |
| `notification_preferences` | User delivery preferences |
| `notification_channels` | Channel-specific settings |
| `notification_history` | Delivery tracking and timestamps |
| `digests` | Daily digest compilation records |
| `bundled_notifications` | Grouped notification containers |
| `notification_bundle_items` | Individual items within bundles |

### Legacy Compatibility

The notification service maintains backward compatibility with older notification types:

```python
# Legacy function maps old notification_type to new (channel, priority) system
service.create_notification_legacy(
    user_id='S-12345',
    notification_type='grade_update',  # Mapped to Academic channel, Medium priority
    message='Your grade has been updated.'
)
```

---

## Configuration

### Database

All three services store data in the main `student_records.db` database. Tables are created automatically on first use.

### Integration Points

| System | Usage |
|--------|-------|
| Authentication | User identity for ownership and permissions |
| Email | Email delivery for notifications and feedback responses |
| Activity Logging | All operations logged for compliance |
| Database | Centralized storage with connection pooling |

### Notification Defaults

| Setting | Default |
|---------|---------|
| Quiet hours | Disabled (set start/end to enable) |
| Bundle window | 300 seconds |
| SMS | High/Urgent priority only |
| Digest | Daily compilation of low-priority items |
| Retention | 90 days (configurable) |

## Troubleshooting

### Lost & Found Matching Not Working

1. Ensure both lost and found items share the same category
2. Check that item details (name, color, brand) are filled in
3. Lower the match threshold if needed
4. Verify dates are within a reasonable range

### Feedback Votes Not Counting

1. Each user can only vote once per submission (enforced)
2. Check if the vote was previously removed
3. Verify the user_id is correct and authenticated

### Notifications Not Delivered

1. Check user preferences - the channel may be disabled
2. Verify priority meets the minimum threshold for the channel
3. Check quiet hours settings
4. For SMS, ensure priority is High or Urgent
5. Review the `notification_history` table for delivery status

### Digest Not Generated

1. Ensure there are unread low-priority notifications
2. Check that the digest generation job is running
3. Verify the user has digest delivery enabled

### Notification Bundling Issues

1. Check the bundle time window setting
2. Notifications must be in the same channel to bundle
3. Review `bundled_notifications` and `notification_bundle_items` tables
