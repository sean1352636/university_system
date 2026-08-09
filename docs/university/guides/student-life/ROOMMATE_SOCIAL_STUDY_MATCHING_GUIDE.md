# Roommate Finder, Social Matching & Study Matching Guide

This guide covers the roommate compatibility matching, social interest matching, and study partner/group matching features within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Roommate Finder](#roommate-finder)
- [Social Matching](#social-matching)
- [Study Matching](#study-matching)
- [Integration Points](#integration-points)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

The University Management System provides three matching services designed to connect students with compatible partners for housing, social activities, and academic collaboration. Each service uses profile-based compatibility algorithms to suggest matches based on preferences, interests, and study habits.

**Key files:**
- Roommate Finder: `modules/domain/roommate_finder/services/roommate_service.py`
- Social Matching: `modules/domain/social_matching/services/social_matching_service.py`
- Study Matching: `modules/domain/study_matching/services/study_matching_service.py`

---

## Roommate Finder

### Creating a Roommate Profile

Students create profiles with their housing preferences:

```python
from university_system.modules.domain.roommate_finder.services.roommate_service import (
    RoommateService
)

service = RoommateService()

service.create_profile(
    student_id='S-12345',
    budget_min=500,
    budget_max=800,
    gender_preference='no_preference',
    smoking_preference=False,
    pet_preference=True,
    major='Computer Science',
    year_of_study=2
)
```

### Compatibility Questionnaire

The system includes 14 pre-defined questions across 5 categories. Students answer these to improve match quality:

```python
service.submit_questionnaire(
    student_id='S-12345',
    responses={
        'q1': {'answer': 'early_bird', 'importance': 'high'},
        'q2': {'answer': 'quiet', 'importance': 'medium'},
        'q3': {'answer': 'clean', 'importance': 'high'},
        # ... more responses
    }
)
```

**Question categories:**
- Sleep schedule and habits
- Cleanliness and shared spaces
- Noise and study environment
- Social preferences and guests
- Lifestyle and daily routines

### Compatibility Scoring

The algorithm calculates compatibility on a 0-100 scale:

| Factor | Weight | Description |
|--------|--------|-------------|
| Questionnaire answers | 1.0-2.0x | Weighted by question importance |
| Budget range overlap | Standard | Budget compatibility check |
| Gender preference | Standard | Mutual preference matching |
| Smoking preference | Standard | Smoking compatibility |
| Pet preference | Standard | Pet tolerance matching |
| Major compatibility | Standard | Same/related major bonus |
| Year of study | Standard | Same year preference |

```python
# Calculate compatibility between two students
score = service.calculate_compatibility('S-12345', 'S-67890')
# Returns: {'score': 85.5, 'breakdown': {...}}
```

### Finding Matches

```python
# Find compatible roommates (minimum score: 50.0 default)
matches = service.find_matches(
    student_id='S-12345',
    min_score=60.0  # Optional: override minimum threshold
)

for match in matches:
    print(f"Student: {match['student_id']}, Score: {match['score']}")
```

### Anonymous Messaging

Matched students can communicate anonymously before revealing identities:

```python
# Send a message to a potential roommate
service.send_message(
    sender_id='S-12345',
    recipient_id='S-67890',
    message='Hi! I saw we have similar schedules. Would you like to discuss rooming together?'
)

# Mark messages as read
service.mark_messages_read(
    student_id='S-67890',
    sender_id='S-12345'
)
```

### Profile Statistics

```python
stats = service.get_profile_stats(student_id='S-12345')
# Returns: match count, message count, profile completeness, etc.
```

### Roommate Database Schema

| Table | Purpose |
|-------|---------|
| `roommate_profiles` | Student preferences and housing criteria |
| `compatibility_questions` | Pre-defined questions with weights |
| `compatibility_responses` | Student answers with importance levels |
| `roommate_matches` | Match records with scores and reasons |
| `roommate_messages` | Anonymous message history |

---

## Social Matching

### Adding Interests

Students build interest profiles across 10 categories:

```python
from university_system.modules.domain.social_matching.services.social_matching_service import (
    SocialMatchingService
)

service = SocialMatchingService()

# Add interests with skill/interest level (1-10)
service.add_user_interest(
    user_id='S-12345',
    category='Sports',
    interest_name='Basketball',
    level=8
)

service.add_user_interest(
    user_id='S-12345',
    category='Music',
    interest_name='Guitar',
    level=6
)
```

### Interest Categories

| Category | Examples |
|----------|----------|
| Sports | Basketball, Soccer, Swimming, Running |
| Music | Guitar, Piano, Singing, DJ |
| Arts | Painting, Photography, Sculpture |
| Gaming | Board Games, Video Games, Chess |
| Outdoor | Hiking, Camping, Cycling |
| Technology | Programming, Robotics, 3D Printing |
| Academic | Debate, Math Club, Book Club |
| Career | Entrepreneurship, Networking, Mentoring |
| Travel | Study Abroad, Cultural Exchange |
| Other | Cooking, Volunteering, Film |

### Personality Profile

```python
service.set_personality_profile(
    user_id='S-12345',
    personality_type='Ambivert',  # Introvert, Extrovert, Ambivert
    activity_level='High',         # Low, Moderate, High, Very High
    communication_style='Collaborative'
)
```

### Privacy Settings

Control how your profile appears in matching:

```python
service.set_privacy_settings(
    user_id='S-12345',
    allow_matching=True,
    show_profile=True,
    allow_messages=True,
    show_interests=True,
    match_same_major=False,
    match_same_year=False
)
```

### Finding Interest Matches

```python
matches = service.find_interest_matches(
    user_id='S-12345',
    min_score=30.0  # Default minimum compatibility score
)
```

### Buddy System

```python
# Send a buddy request
service.send_buddy_request(
    sender_id='S-12345',
    recipient_id='S-67890',
    message='Hey! Want to join the intramural basketball team together?'
)

# Find study abroad buddies
buddies = service.find_study_abroad_buddies(
    user_id='S-12345',
    destination='France'
)
```

### Team Formation

```python
# Create an intramural sports team
service.create_team(
    creator_id='S-12345',
    team_name='Code Warriors',
    sport='Basketball',
    max_members=10
)

# Join an existing team (checks capacity)
service.join_team(
    user_id='S-67890',
    team_id='team_001'
)
```

### Club Recommendations

```python
# AI-powered club suggestions based on interests
recommendations = service.generate_club_recommendations(user_id='S-12345')
```

### Social Activities

```python
# Create a social event
service.create_social_activity(
    creator_id='S-12345',
    activity_name='Weekend Hike',
    activity_type='Outdoor',
    date='2025-11-15',
    max_participants=20
)

# Join an activity (RSVP)
service.join_activity(
    user_id='S-67890',
    activity_id='act_001'
)
```

### Social Matching Database Schema

| Table | Purpose |
|-------|---------|
| `user_interests` | Interest tracking with levels (1-10) |
| `user_personality` | Personality profile data |
| `user_privacy_settings` | Privacy and matching controls |
| `interest_matches` | Saved interest-based matches |
| `buddy_requests` | Buddy connection requests |
| `team_formations` | Sports team creation |
| `team_members` | Team membership records |
| `social_activities` | Social events |
| `activity_participants` | Event attendance and RSVP |

---

## Study Matching

### Creating a Study Profile

```python
from university_system.modules.domain.study_matching.services.study_matching_service import (
    StudyMatchingService
)

service = StudyMatchingService()

service.create_study_profile(
    student_id='S-12345',
    study_style='Visual',           # Visual, Auditory, Kinesthetic, Reading/Writing
    group_size='Small (2-4)',       # Solo, Small (2-4), Medium (5-8), Large (9+)
    communication='Collaborative',   # Collaborative, Independent, Mixed
    noise_preference='Quiet',        # Quiet, Moderate, Lively
    availability='Weekday evenings',
    interests='Data Structures, Algorithms, Machine Learning'
)
```

### Finding Study Partners

```python
matches = service.find_study_matches(student_id='S-12345')

for match in matches:
    print(f"Partner: {match['student_id']}, Compatibility: {match['score']}")
```

### Study Groups

```python
# Create a study group for a specific course
service.create_study_group(
    creator_id='S-12345',
    course_id='CS201',
    group_name='Algorithms Study Group',
    max_members=6,
    description='Weekly study sessions for CS201 Algorithms'
)

# Join an existing group (checks capacity)
service.join_study_group(
    student_id='S-67890',
    group_id='grp_001'
)
```

### Virtual Study Rooms

Create online study spaces with built-in Pomodoro timer:

```python
# Create a virtual study room
service.create_virtual_study_room(
    creator_id='S-12345',
    room_name='Late Night Study Session',
    work_duration=25,   # Pomodoro work period (minutes)
    break_duration=5    # Pomodoro break period (minutes)
)
# Returns: room_code for sharing

# Join with room code
service.join_virtual_study_room(
    student_id='S-67890',
    room_code='ABC123'
)

# Leave the room
service.leave_virtual_study_room(
    student_id='S-67890',
    room_id='room_001'
)
```

### Pomodoro Sessions

Track focused study time with the built-in Pomodoro technique:

```python
# Start a Pomodoro session
service.start_pomodoro_session(
    student_id='S-12345',
    room_id='room_001'
)

# Complete and log the session
service.complete_pomodoro_session(
    session_id='pom_001'
)
# Tracks: work duration, completion status, participant statistics
```

### Q&A Board

Anonymous question and answer system for academic help:

```python
# Post a question
service.post_question(
    student_id='S-12345',
    course_id='CS201',
    title='How does Dijkstra\'s algorithm handle negative weights?',
    body='I understand the basic algorithm but...',
    is_anonymous=True
)

# Post an answer
service.post_answer(
    student_id='S-67890',
    question_id='q_001',
    body='Dijkstra\'s algorithm does not handle negative weights...',
    is_anonymous=False
)

# Vote on content (upvote/downvote)
service.vote_on_content(
    student_id='S-11111',
    content_type='answer',
    content_id='a_001',
    vote_type='upvote'
)

# Mark the best answer
service.mark_answer_accepted(
    question_id='q_001',
    answer_id='a_001',
    student_id='S-12345'  # Must be the question author
)
```

### Study Analytics

```python
analytics = service.get_study_matching_analytics(student_id='S-12345')
# Returns:
#   - Total study hours (Pomodoro sessions)
#   - Study group participation
#   - Q&A contributions
#   - Match history
#   - Study streak data
```

### Study Matching Database Schema

| Table | Purpose |
|-------|---------|
| `study_profiles` | Learning styles, preferences, availability |
| `study_groups` | Course-based study groups |
| `study_group_members` | Membership with roles |
| `virtual_study_rooms` | Online study spaces with Pomodoro settings |
| `study_room_participants` | Room attendance tracking |
| `pomodoro_sessions` | Work/break session records |
| `qa_board` | Anonymous Q&A questions |
| `qa_answers` | Answer records |
| `qa_votes` | Upvote/downvote history |
| `study_match_suggestions` | Algorithmic match suggestions |

---

## Integration Points

All three matching services integrate with:

| System | Usage |
|--------|-------|
| Authentication | `get_auth()` for user identity and permissions |
| Database | `get_connection()` / `transaction()` for data access |
| Activity Logging | `log_activity()` for all matching operations |
| Email | `send_email()` for match notifications |
| i18n | Multi-language support for UI text |

## Configuration

### Matching Thresholds

| Service | Default Minimum Score | Range |
|---------|----------------------|-------|
| Roommate Finder | 50.0 | 0-100 |
| Social Matching | 30.0 | 0-100 |
| Study Matching | Varies | 0-100 |

### Database

All matching data is stored in the main `student_records.db` database. Tables are created on first use via each service's initialization method.

### Privacy Defaults

All matching services default to:
- Matching enabled
- Profile visible
- Messages allowed
- Anonymous communication available for roommate matching

## Troubleshooting

### No Matches Found

1. Verify the student has a complete profile
2. Lower the minimum compatibility score threshold
3. Check that other students have profiles in the system
4. Ensure privacy settings allow matching (`allow_matching=True`)

### Compatibility Score Seems Low

1. Complete the compatibility questionnaire (roommate finder)
2. Add more interests to the profile (social matching)
3. Fill in all study preferences (study matching)
4. Higher importance weights increase score differentiation

### Messages Not Delivered

1. Verify both users have matching profiles
2. Check privacy settings for message permissions
3. Ensure the recipient's profile is active
4. Review the `roommate_messages` table for delivery status

### Study Group Full

1. Check the group's `max_members` setting
2. The creator can increase capacity
3. Create a new group for the same course
4. Use the Q&A board for larger-scale collaboration

### Virtual Study Room Issues

1. Verify the room code is correct
2. Check if the room is still active
3. Ensure the student is authenticated
4. Room creators can manage participants
