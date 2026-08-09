# Secondary School -- REST API Reference

This document describes the Flask REST API for the Secondary School Management System.

---

## Server Setup

The API uses a Flask **app factory** pattern defined in `shared/api/secondary/api_server.py`:

```python
from education_system.shared.api.secondary.api_server import create_app

app = create_app(db_path)
```

**Starting the server:**

```bash
python run.py school --api
# or
python -m education_system.secondary_school --api
```

Default: `http://localhost:5002/api`

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
    "username": "admin2",
    "password": "admin1234"
}
```

**Response:**
```json
{
    "token": "eyJ...",
    "user": {
        "id": 1,
        "username": "admin2",
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
GET /api/students?page=1&per_page=25
```

**Response includes:**
```json
{
    "items": [...],
    "total": 150,
    "page": 1,
    "per_page": 25,
    "pages": 6
}
```

---

## API Endpoints

### Academics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/students` | List / create students |
| GET/PUT/DELETE | `/api/students/<id>` | Get / update / delete student |
| GET/POST | `/api/subjects` | List / create subjects |
| GET/PUT/DELETE | `/api/subjects/<id>` | Get / update / delete subject |
| GET/POST | `/api/enrollment` | List / create enrollments |
| GET/POST | `/api/grades` | List / record grades |
| GET/POST | `/api/attendance` | List / record attendance |
| GET/POST | `/api/timetable` | List / create timetable slots |
| GET/POST | `/api/homework` | List / create homework |
| GET/POST | `/api/exams` | List / create exams |
| GET | `/api/progress/<student_id>` | Get student progress |
| GET/POST | `/api/reports` | List / generate reports |
| GET/POST | `/api/interventions` | List / create interventions |

### Pastoral Care

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/behaviour` | List / record behaviour incidents |
| GET/POST | `/api/detentions` | List / create detentions |
| GET/POST | `/api/exclusions` | List / create exclusions |
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

### Student Life

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/clubs` | List / create clubs |
| GET/POST | `/api/library` | List / manage library items |
| GET/POST | `/api/meals` | List / manage meal choices |
| GET/POST | `/api/transport` | List / manage transport |
| GET/POST | `/api/trips` | List / create trips |
| GET/POST | `/api/medical` | List / create medical records |
| GET/POST | `/api/careers` | List / create careers records |
| GET/POST | `/api/consent` | List / manage consent forms |

### Facilities

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/room-booking` | List / create room bookings |
| GET/POST | `/api/assets` | List / manage assets |
| GET/POST | `/api/visitors` | List / register visitors |
| GET/POST | `/api/incidents` | List / report incidents |
| GET/POST | `/api/seating-plans` | List / create seating plans |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/system/health` | Health check |
| GET | `/api/system/version` | System version info |
