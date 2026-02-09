# Real-Time Collaboration Features

This module provides comprehensive real-time collaboration capabilities for the University Management System using WebSocket technology.

## Features

### 1. **WebSocket Infrastructure**
- Persistent bi-directional communication
- Automatic reconnection handling
- Connection pooling and management
- Room-based messaging
- Message type routing

### 2. **Real-Time Notifications**
- Instant notifications for:
  - Grade updates
  - Assignment postings
  - Enrollment confirmations
  - Payment receipts
  - System alerts
- Priority levels (low, medium, high, urgent)
- Read/unread tracking
- Notification history

### 3. **User Presence Tracking**
- Online/offline status
- Away detection (auto after 5 minutes)
- Custom status messages
- Activity tracking
- Presence visibility controls

### 4. **Live Chat Support**
- Direct messaging (1-on-1)
- Group chats
- Support ticket chats
- Course discussion rooms
- Message history
- Read receipts
- Typing indicators (via cursor updates)

### 5. **Collaborative Document Editing**
- Real-time document synchronization
- Operational transformation for conflict resolution
- Live cursor positions
- Edit history tracking
- Multi-user collaboration
- Document types: assignments, notes, projects, whiteboards

### 6. **Activity Stream**
- Real-time activity feed
- Activity types: grades, assignments, enrollments, announcements
- Like and comment on activities
- Filtered subscriptions
- Visibility controls (public, course, department, private)

### 7. **Dashboard Updates**
- Live metric updates
- System status broadcasts
- Custom alerts
- Subscription-based updates
- Multiple metric tracking

## Architecture

```
┌─────────────────────────────────────────────┐
│         Client (Web/Mobile App)             │
└─────────────────┬───────────────────────────┘
                  │ WebSocket Connection
                  │ (wss://host/api/v1/ws?token=...)
┌─────────────────▼───────────────────────────┐
│      WebSocket Manager (Hub)                │
│  - Connection Management                    │
│  - Message Routing                          │
│  - Room Management                          │
└─────────────────┬───────────────────────────┘
                  │
        ┌─────────┴─────────┬──────────┬──────────┐
        ▼                   ▼          ▼          ▼
┌───────────────┐  ┌─────────────┐  ┌──────┐  ┌──────┐
│ Notifications │  │    Chat     │  │ Collab│  │Activity│
│   Service     │  │   Service   │  │Service│  │Stream│
└───────────────┘  └─────────────┘  └──────┘  └──────┘
```

## Quick Start

### 1. Connect to WebSocket

**JavaScript Client:**
```javascript
// Get JWT token from login
const token = localStorage.getItem('auth_token');

// Connect to WebSocket
const ws = new WebSocket(`wss://university.example.com/api/v1/ws?token=${token}`);

ws.onopen = () => {
    console.log('Connected to real-time service');
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    handleMessage(message);
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('Disconnected from real-time service');
};

function handleMessage(message) {
    switch(message.type) {
        case 'notification':
            showNotification(message);
            break;
        case 'chat_message':
            displayChatMessage(message);
            break;
        case 'presence_update':
            updateUserStatus(message);
            break;
        case 'dashboard_update':
            updateDashboard(message);
            break;
        case 'document_update':
            syncDocument(message);
            break;
        case 'activity':
            addToActivityFeed(message);
            break;
    }
}
```

**Python Client:**
```python
import asyncio
import websockets
import json

async def connect_realtime(token):
    uri = f"ws://localhost:8000/api/v1/ws?token={token}"

    async with websockets.connect(uri) as websocket:
        # Receive connection confirmation
        response = await websocket.recv()
        print(f"Connected: {response}")

        # Listen for messages
        async for message in websocket:
            data = json.loads(message)
            print(f"Received: {data['type']}")
            handle_message(data)

def handle_message(message):
    msg_type = message.get('type')
    if msg_type == 'notification':
        print(f"Notification: {message['title']}")
    elif msg_type == 'chat_message':
        print(f"Chat: {message['sender_id']}: {message['text']}")
    # ... handle other message types

# Run client
asyncio.run(connect_realtime("your-jwt-token"))
```

### 2. Send Notifications

```python
import requests

# Send notification via HTTP API
response = requests.post(
    "http://localhost:8000/api/v1/realtime/notifications/send",
    json={
        "title": "New Grade Posted",
        "message": "Your grade for Assignment 1 is now available",
        "category": "grade",
        "priority": "high",
        "user_ids": ["student123"],
        "data": {
            "course": "CS101",
            "grade": "A",
            "assignment": "Assignment 1"
        }
    }
)
```

### 3. Create Chat Room

```python
import requests

# Create a support chat room
response = requests.post(
    "http://localhost:8000/api/v1/realtime/chat/rooms/create",
    json={
        "room_id": "support_ticket_456",
        "room_type": "support",
        "participants": ["student123", "support_staff_789"],
        "room_name": "Support Chat - Ticket #456"
    }
)

# Send message in chat
requests.post(
    "http://localhost:8000/api/v1/realtime/chat/messages/send",
    json={
        "room_id": "support_ticket_456",
        "sender_id": "student123",
        "message_text": "I need help with my enrollment",
        "message_type": "text"
    }
)
```

### 4. Collaborative Document Editing

```python
import requests

# Create collaborative document
response = requests.post(
    "http://localhost:8000/api/v1/realtime/collaboration/documents/create",
    json={
        "document_id": "assignment_collab_123",
        "document_type": "assignment",
        "owner_id": "student123",
        "title": "Group Project Notes",
        "initial_content": "# Group Project\n\n## Members\n- Student A\n- Student B"
    }
)

# Join document for collaboration
requests.post(
    "http://localhost:8000/api/v1/realtime/collaboration/documents/join",
    json={
        "document_id": "assignment_collab_123",
        "user_id": "student456"
    }
)

# Apply edit operation
requests.post(
    "http://localhost:8000/api/v1/realtime/collaboration/documents/operation",
    json={
        "document_id": "assignment_collab_123",
        "user_id": "student456",
        "operation_type": "insert",
        "position": 50,
        "content": "- Student C\n"
    }
)
```

### 5. Activity Stream

```python
import requests

# Post activity to stream
response = requests.post(
    "http://localhost:8000/api/v1/realtime/activity/post",
    json={
        "activity_type": "assignment_submitted",
        "user_id": "student123",
        "title": "Assignment Submitted",
        "description": "Student submitted CS101 Assignment 1",
        "visibility": "course",
        "course_id": "CS101"
    }
)

# Subscribe to activity updates
requests.post(
    "http://localhost:8000/api/v1/realtime/activity/subscribe/student123"
)

# Get activity feed
response = requests.get(
    "http://localhost:8000/api/v1/realtime/activity/feed/student123?limit=50"
)
activities = response.json()['activities']
```

## Integration with Existing Features

### Grade Updates

```python
# In your grade posting code
from university_system.infrastructure.realtime import get_notification_service

async def post_grade(student_id, course_name, grade):
    # ... save grade to database ...

    # Send real-time notification
    notification_service = get_notification_service()
    await notification_service.notify_grade_update(
        student_id=student_id,
        course_name=course_name,
        grade=grade
    )
```

### Assignment Notifications

```python
from university_system.infrastructure.realtime import get_notification_service

async def create_assignment(course_id, assignment_name, due_date):
    # ... create assignment in database ...

    # Get enrolled students
    student_ids = get_enrolled_students(course_id)

    # Send notifications
    notification_service = get_notification_service()
    await notification_service.notify_assignment_posted(
        student_ids=student_ids,
        course_name=course_id,
        assignment_name=assignment_name,
        due_date=due_date
    )
```

### Dashboard Metrics

```python
from university_system.infrastructure.realtime import get_dashboard_service, DashboardMetric

async def update_student_count():
    # Get current count from database
    count = get_total_students()

    # Update dashboard
    dashboard_service = get_dashboard_service()
    await dashboard_service.update_metric(
        metric=DashboardMetric.STUDENT_COUNT,
        value=count
    )
```

## Message Types

### Connection Messages
- `connect` - Connection established
- `disconnect` - Connection closed
- `ping` / `pong` - Keep-alive messages

### Notification Messages
```json
{
    "type": "notification",
    "notification_id": "student123_1234567890",
    "title": "New Grade Posted",
    "message": "Your grade for Assignment 1 is available",
    "category": "grade",
    "priority": "high",
    "data": {"course": "CS101", "grade": "A"},
    "timestamp": "2025-02-01T12:00:00Z"
}
```

### Chat Messages
```json
{
    "type": "chat_message",
    "message_id": "room123_1234567890",
    "room_id": "room123",
    "sender_id": "user456",
    "text": "Hello, I need help",
    "message_type": "text",
    "timestamp": "2025-02-01T12:00:00Z"
}
```

### Presence Updates
```json
{
    "type": "presence_update",
    "user_id": "student123",
    "status": "online",
    "status_message": "Working on assignment",
    "timestamp": "2025-02-01T12:00:00Z"
}
```

### Document Updates
```json
{
    "type": "document_update",
    "document_id": "doc123",
    "update_type": "operation",
    "operation": {
        "type": "insert",
        "position": 50,
        "content": "New text",
        "user_id": "student456"
    },
    "timestamp": "2025-02-01T12:00:00Z"
}
```

### Activity Feed
```json
{
    "type": "activity",
    "activity_id": "act_1234567890",
    "activity_type": "grade_posted",
    "user_id": "instructor123",
    "title": "Grades Posted",
    "description": "Final grades for CS101 are now available",
    "visibility": "course",
    "course_id": "CS101",
    "timestamp": "2025-02-01T12:00:00Z"
}
```

## Performance Considerations

- **Connection Pooling**: WebSocket connections are pooled and reused
- **Message Batching**: Multiple updates can be batched together
- **Room-based Broadcasting**: Messages only sent to relevant users
- **History Limits**: Message and activity history is automatically trimmed
- **Memory Management**: In-memory storage with configurable limits

## Security

- **JWT Authentication**: All WebSocket connections require valid JWT token
- **Authorization**: Message delivery respects user permissions
- **Rate Limiting**: WebSocket messages are rate-limited
- **Input Validation**: All messages are validated before processing
- **CORS Protection**: WebSocket upgrades respect CORS settings

## Monitoring

### Get Statistics
```python
import requests

# Get WebSocket statistics
response = requests.get("http://localhost:8000/api/v1/ws/stats")
stats = response.json()

print(f"Total users online: {stats['websocket']['total_users']}")
print(f"Total connections: {stats['websocket']['total_connections']}")
print(f"Active rooms: {stats['websocket']['total_rooms']}")
```

### Health Check
```python
# Check online users
response = requests.get("http://localhost:8000/api/v1/ws/online-users")
online_users = response.json()['online_users']
```

## Best Practices

1. **Always authenticate**: Include JWT token in WebSocket connection
2. **Handle reconnections**: Implement exponential backoff for reconnects
3. **Validate messages**: Check message types and structure
4. **Clean up**: Close connections when no longer needed
5. **Subscribe wisely**: Only subscribe to needed updates
6. **Use rooms**: Group related users in rooms for efficient broadcasting
7. **Batch updates**: When possible, batch multiple updates together
8. **Handle offline**: Implement offline message queuing if needed

## Troubleshooting

### Connection Issues
- Verify JWT token is valid and not expired
- Check CORS settings for WebSocket upgrade
- Ensure server is running and accessible
- Check firewall/proxy WebSocket support

### Message Not Received
- Verify user is subscribed to message type
- Check user permissions for message visibility
- Confirm WebSocket connection is active
- Review message routing logic

### Performance Issues
- Reduce broadcast frequency
- Limit message history size
- Use room-based messaging
- Implement message throttling

## API Reference

See individual service documentation:
- [WebSocket Manager](websocket_manager.py)
- [Notification Service](notification_service.py)
- [Presence Manager](presence_manager.py)
- [Chat Service](chat_service.py)
- [Collaboration Service](collaboration_service.py)
- [Activity Stream](activity_stream.py)
- [Dashboard Service](dashboard_service.py)

## Examples

See `/examples/realtime_demo.py` for complete working examples.

## Support

For issues or questions:
- Check the documentation
- Review example code
- Check WebSocket connection logs
- Contact system administrator
