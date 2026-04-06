# Primary School -- REST API Reference

This document describes the Flask REST API for the Primary School Management System.

---

## Server Setup

The API uses a Flask **app factory** pattern defined in `shared/api/primary/api_server.py`:

```python
from education_system.shared.api.primary.api_server import create_app

app = create_app(db_path)
```

**Starting the server:**

```bash
python run.py primary --api
# or
python -m education_system.primary_school --api
```

Default: `http://localhost:5003/api`

---

## Authentication

All endpoints (except `/api/auth/login`) require a JWT token in the `Authorization` header:

```
Authorization: Bearer <token>
```

### Login

```
POST /api/auth/login
Content-Type: application/json

{
    "username": "admin3",
    "password": "admin1234"
}
```

**Response:**
```json
{
    "token": "eyJ...",
    "user": {
        "id": 1,
        "username": "admin3",
        "role": "admin"
    }
}
```

---

## Error Handling

All errors return JSON with an `error` key:

```json
{
    "error": "Resource not found"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad request / validation error |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient role) |
| 404 | Resource not found |
| 409 | Conflict (duplicate entry) |
| 500 | Internal server error |

---

## Pagination

List endpoints support pagination via query parameters:

```
GET /api/pupils?page=1&per_page=25
```

**Response includes:**
```json
{
    "items": [...],
    "total": 120,
    "page": 1,
    "per_page": 25,
    "pages": 5
}
```

---

## API Endpoints

### Academics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/pupils` | List / create pupils |
| GET/PUT/DELETE | `/api/pupils/<id>` | Get / update / delete pupil |
| GET/POST | `/api/subjects` | List / create subjects |
| GET/POST | `/api/classes` | List / create classes |
| GET/POST | `/api/assessment` | List / record assessments |
| GET/POST | `/api/attendance` | List / record attendance |
| GET/POST | `/api/timetable` | List / create timetable slots |
| GET/POST | `/api/homework` | List / create homework |
| GET/POST | `/api/sats` | List / record SATs results |
| GET/POST | `/api/phonics` | List / record phonics screening |
| GET/POST | `/api/reading-records` | List / create reading records |
| GET | `/api/progress/<pupil_id>` | Get pupil progress |
| GET/POST | `/api/class-groups` | List / manage class groups |

### Pastoral Care

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/behaviour` | List / record behaviour incidents |
| GET/POST | `/api/rewards` | List / award rewards |
| GET/POST | `/api/pastoral` | List / create pastoral notes |
| GET/POST | `/api/safeguarding` | List / create safeguarding concerns |
| GET/POST | `/api/send` | List / create SEND records |

### Staff

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/hr/staff` | List / create staff |
| GET/POST | `/api/cpd` | List / create CPD records |
| GET/POST | `/api/cover` | List / create cover arrangements |
| GET | `/api/staff-directory` | Staff directory listing |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/admissions` | List / create applications |
| GET/POST | `/api/finance` | List / create transactions |
| GET/POST | `/api/policies` | List / create policies |
| GET/POST | `/api/documents` | List / upload documents |
| GET | `/api/audit-log` | Audit log entries |
| GET/POST | `/api/users` | List / create user accounts |
| GET/PUT | `/api/settings` | Get / update system settings |
| POST | `/api/data-export` | Export data |

### Communication

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/announcements` | List / create announcements |
| GET/POST | `/api/calendar` | List / create calendar events |
| GET/POST | `/api/email` | List / send emails |
| GET/POST | `/api/notifications` | List / create notifications |
| GET/POST | `/api/parents-evening` | List / create evening bookings |
| GET/POST | `/api/communication-log` | List / create comms log entries |

### Pupil Life

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/clubs` | List / create clubs |
| GET/POST | `/api/library` | List / manage library items |
| GET/POST | `/api/meals` | List / manage meal choices |
| GET/POST | `/api/transport` | List / manage transport |
| GET/POST | `/api/trips` | List / create trips |
| GET/POST | `/api/medical` | List / create medical records |
| GET/POST | `/api/consent` | List / manage consent forms |

### Facilities

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/room-booking` | List / create room bookings |
| GET/POST | `/api/assets` | List / manage assets |
| GET/POST | `/api/visitors` | List / register visitors |
| GET/POST | `/api/incidents` | List / report incidents |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/system/health` | Health check |
| GET | `/api/system/version` | System version info |
