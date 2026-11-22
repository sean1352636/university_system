# Primary School -- REST API Reference

This document describes the Flask REST API for the Primary School Management System.

---

## Server Setup

The Primary School has no API server of its own. The unified server in `src/education_system/platform/delivery/api/unified_server.py` hosts every system, and mounts the blueprints from `src/education_system/api/primary/routes/` (its `ALL_BLUEPRINTS`):

```python
from education_system.platform.delivery.api.unified_server import create_unified_app

app = create_unified_app()
```

**Starting the server:**

```bash
python -m education_system --primary --api
```

Default: `http://localhost:5000/api/v1/primary` (set the port with `API_PORT`)

---

## Authentication

All endpoints require a JWT token in the `Authorization` header. Login itself is served by the unified server, not under the primary prefix:

```
Authorization: Bearer <token>
```

### Login

```
POST /api/v1/auth/login
Content-Type: application/json

{
    "username": "admin3",
    "password": "admin1234"
}
```

The response carries the token to send on later requests.

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

## List Responses

Primary list endpoints are not paginated. They filter through query parameters and return the matching records with a count:

```
GET /api/v1/primary/clubs?active_only=1
```

**Response includes:**
```json
{
    "items": [...],
    "count": 12
}
```

---

## API Endpoints

Every path below is relative to `/api/v1/primary`. Each is a blueprint in `src/education_system/api/primary/routes/`; see that module for its methods and sub-routes.

### Pupils and Admissions

| Endpoint | Description |
|----------|-------------|
| `/pupils` | Pupil records |
| `/admissions` | Applications |
| `/enrolment` | Year group enrolment |
| `/parent-contacts` | Parent and guardian contacts |

### Academics

| Endpoint | Description |
|----------|-------------|
| `/academic-year` | Academic years and terms |
| `/calendar` | Calendar events |
| `/year-groups` | Year groups |
| `/classes` | Classes |
| `/subjects` | Subjects |
| `/timetable` | Timetable slots |
| `/attendance` | Attendance registers |
| `/lesson-plans` | Lesson plans |
| `/homework` | Homework |
| `/library` | Library items and loans |
| `/clubs` | Clubs and memberships |

### Assessment and Progress

| Endpoint | Description |
|----------|-------------|
| `/assessment` | Assessment records |
| `/phonics` | Phonics tracking |
| `/phonics-screening` | Phonics screening check |
| `/reading-levels` | Reading levels |
| `/mtc` | Multiplication tables check |
| `/ks1-sats` | KS1 SATs results |
| `/ks2-sats` | KS2 SATs results |
| `/eyfs-profile` | EYFS profile results |
| `/target-setting` | Pupil targets |
| `/intervention-tracking` | Interventions |
| `/early-warning` | Early warning alerts |
| `/observations` | Observations |
| `/progress` | Progress reviews |
| `/progress-report` | Progress reporting |
| `/pupil-reports` | Pupil reports |

### Pastoral and Wellbeing

| Endpoint | Description |
|----------|-------------|
| `/behaviour` | Behaviour incidents |
| `/house-points` | House points |
| `/safeguarding` | Safeguarding concerns |
| `/prevent-duty` | Prevent referrals |
| `/send` | SEND records |
| `/pupil-premium` | Pupil premium |
| `/accessibility` | Accessibility arrangements |
| `/wellbeing` | Wellbeing check-ins |
| `/pupil-support` | Support plans |
| `/attendance-concerns` | Attendance concerns |
| `/absence-requests` | Absence requests |
| `/first-aid` | First aid incidents |
| `/medical-records` | Medical records |
| `/emergency` | Emergency events |
| `/equality-diversity` | Equality and diversity incidents |
| `/complaints` | Complaints |
| `/feedback` | Feedback |
| `/surveys` | Surveys |
| `/school-council` | School council |
| `/wraparound` | Breakfast and after-school clubs |
| `/transport` | Transport |

### Staff

| Endpoint | Description |
|----------|-------------|
| `/staff` | Staff directory |
| `/class-teachers` | Class teacher assignments |
| `/teaching-assistants` | Teaching assistants |
| `/staff-hr` | HR records |
| `/staff-absence` | Staff absence |
| `/staff-wellbeing` | Staff wellbeing |
| `/recruitment` | Recruitment |
| `/appraisals` | Appraisals |
| `/cpd` | CPD records |
| `/dbs-checks` | DBS checks |
| `/cover` | Cover arrangements |
| `/departments` | Departments |

### Communication

| Endpoint | Description |
|----------|-------------|
| `/announcements` | Announcements |
| `/notifications` | Notifications |
| `/activity-feed` | Activity feed |
| `/messages` | Messages |
| `/newsletters` | Newsletters |
| `/parents-evenings` | Parents' evenings and bookings |
| `/letter-templates` | Letter templates |
| `/document-hub` | Documents |
| `/attachments` | Attachments |
| `/visitors` | Visitors |

### Finance

| Endpoint | Description |
|----------|-------------|
| `/dinner-money` | Dinner money ledger |
| `/trips` | Trips and payments |
| `/receipts` | Receipts |
| `/expense-claims` | Expense claims |
| `/funding` | Funding streams and allocations |
| `/census` | School census returns |

### Reports

| Endpoint | Description |
|----------|-------------|
| `/attendance-report` | Attendance reporting |
| `/kpi-dashboard` | KPI dashboard |
| `/data-dashboard` | Data dashboard |
| `/mobile-dashboard` | Mobile dashboard |
| `/audit-reports` | Audit reports |
| `/data-export` | Data export |
| `/custom-export` | Custom export |

### Governance and System

| Endpoint | Description |
|----------|-------------|
| `/compliance` | Compliance items |
| `/governance` | Governors and meetings |
| `/policies` | Policies |
| `/gdpr` | GDPR requests, consents and breaches |
| `/risk-management` | Risks |
| `/health-safety` | Health and safety incidents |
| `/assets` | Assets |
| `/user-management` | User accounts |
| `/todo` | To-do items |
| `/menu/<category>` | Routes that back each main-menu category |

### Server

These are served by the unified server, outside the primary prefix.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/systems` | Mounted systems and any mount errors |
