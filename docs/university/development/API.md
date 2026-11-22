# REST API Reference

The University Management System exposes a comprehensive REST API via Flask, mounted by the unified API server. University endpoints are prefixed with `/api/v1/university/`; sign-in and health routes are shared by all seven systems and sit at `/api/v1/`.

## Base URL

```
http://localhost:5000/api/v1
```

Configure the host and port with the `API_HOST` and `API_PORT` environment variables.

## Authentication

The API uses **JWT Bearer tokens** for authentication.

### Login Flow

```
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "student001",
  "password": "your_password"
}
```

Response:
```json
{
  "message": "Login successful.",
  "token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "user_id": 1,
    "username": "student001",
    "display_name": "student001",
    "systems": [...],
    "password_expired": false,
    "must_change_password": false
  }
}
```

### Using the Token

Include the token in the `Authorization` header for all subsequent requests:

```
Authorization: Bearer eyJ...
```

### Refreshing Tokens

```
POST /api/v1/auth/refresh
Authorization: Bearer <current_token>
```

## Common Patterns

### Pagination

Most list endpoints support pagination:

```
GET /api/v1/university/students?page=1&per_page=20
```

Response includes pagination metadata:
```json
{
  "items": [...],
  "page": 1,
  "per_page": 20,
  "total": 150,
  "pages": 8
}
```

### Search and Filtering

Use query parameters to filter results:

```
GET /api/v1/university/courses?department=CS&level=300&search=algorithms
```

### Error Responses

All errors follow a consistent format:

```json
{
  "error": "not_found",
  "message": "Student with ID 999 not found",
  "status": 404
}
```

Common status codes:
| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 400 | Bad request / validation error |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

### Rate Limiting

Requests are rate-limited per IP. When exceeded, the API returns `429 Too Many Requests` with a `Retry-After` header.

---

## Endpoints

### Auth & Users

| Prefix | Description |
|---|---|
| `/api/v1/auth` | Login, logout, token refresh, current user info |

### Academic Core

| Prefix | Description |
|---|---|
| `/api/v1/university/courses` | Course catalog, CRUD, and waitlist management |
| `/api/v1/university/students` | Student profiles and record management |
| `/api/v1/university/grades` | Grade recording, updates, and transcripts |
| `/api/v1/university/attendance` | Session tracking and attendance records |
| `/api/v1/university/assignments` | Assignment CRUD, submissions, and grading |
| `/api/v1/university/assessments` | Module assessments and evaluations |
| `/api/v1/university/exams` | Exam scheduling and accommodations |
| `/api/v1/university/modules` | Course/subject creation, updates, and management |
| `/api/v1/university/timetable` | Module schedules and student timetables |
| `/api/v1/university/evaluations` | Course evaluations and feedback submissions |

### Finance

| Prefix | Description |
|---|---|
| `/api/v1/university/finance` | Fees, payments, and account balances |
| `/api/v1/university/financial-aid` | Aid applications, packages, and payment plans |
| `/api/v1/university/scholarships` | Scholarship listings and applications |

### Student Life

| Prefix | Description |
|---|---|
| `/api/v1/university/clubs` | Student club management and memberships |
| `/api/v1/university/events` | Campus event creation and registrations |
| `/api/v1/university/elections` | Polls, candidates, votes, and union representatives |
| `/api/v1/university/study-groups` | Study group creation and memberships |
| `/api/v1/university/mentorship` | Mentor relationships and session tracking |
| `/api/v1/university/dining` | Meal accounts, transactions, and menu items |
| `/api/v1/university/lost-found` | Lost item reporting and claims |
| `/api/v1/university/equipment` | Equipment checkouts, rentals, and maintenance |

### Campus & Facilities

| Prefix | Description |
|---|---|
| `/api/v1/university/campus` | Buildings, rooms, tours, and resource bookings |
| `/api/v1/university/housing` | Accommodation applications and room assignments |
| `/api/v1/university/accommodations` | Disability and accessibility services |
| `/api/v1/university/parking` | Parking permits, spaces, and vehicles |
| `/api/v1/university/facilities` | Facility booking and maintenance requests |
| `/api/v1/university/security` | Security desk tickets and incident management |
| `/api/v1/university/emergency` | Emergency alerts, contacts, and incidents |

### Health & Counseling

| Prefix | Description |
|---|---|
| `/api/v1/university/health-services` | Medical appointments and health records |
| `/api/v1/university/counseling` | Mental health appointments and crisis resources |

### Career & Alumni

| Prefix | Description |
|---|---|
| `/api/v1/university/career` | Job postings, applications, and internships |
| `/api/v1/university/alumni` | Alumni profiles, events, and donations |
| `/api/v1/university/advising` | Academic advising appointments |

### Support & Communication

| Prefix | Description |
|---|---|
| `/api/v1/university/helpdesk` | Support tickets, KB articles, and FAQs |

### Administration

| Prefix | Description |
|---|---|
| `/api/v1/university/hr` | Staff, departments, leave, shifts, timesheets, and appraisals |
| `/api/v1/university/credentials` | Blockchain credentials, badges, and certifications |
| `/api/v1/university/degrees` | Degree programs, requirements, and prerequisites |

### Academic Services

| Prefix | Description |
|---|---|
| `/api/v1/university/admissions` | Prospect management and admission applications |
| `/api/v1/university/enrollments` | Course enrollment and module registration |
| `/api/v1/university/library` | Book catalog, loans, and reservations |
| `/api/v1/university/integrity` | Academic misconduct cases, plagiarism, and AI detection |
| `/api/v1/university/virtual-classrooms` | Virtual classrooms, sessions, and recordings |
| `/api/v1/university/office-hours` | Office hour scheduling and booking |
| `/api/v1/university/teaching-assistants` | TA assignments and permissions |
| `/api/v1/university/tutoring` | Peer tutoring offers |
| `/api/v1/university/early-warning` | Student risk profiles and interventions |
| `/api/v1/university/parents` | Parent portal accounts and student links |
| `/api/v1/university/research` | Research projects and publications |
| `/api/v1/university/calendar` | Academic calendar and events |

### System

| Prefix | Description |
|---|---|
| `/api/v1/health` | Health check (also `/health/ready` and `/health/live`) |

---

## Running the API Server

```bash
# Start the unified API server (all systems)
python -m education_system --university --api

# Or via make
make run-api
```

The server starts on `http://localhost:5000` by default. University settings are loaded from `var/data/university/config/api_server_config.json`.

## CORS

Cross-Origin Resource Sharing is configured via the `CORS_ALLOWED_ORIGINS` environment variable (comma-separated list of origins). Defaults to `http://localhost:3000`.

```bash
export CORS_ALLOWED_ORIGINS="http://localhost:3000,https://your-frontend.example.com"
```
