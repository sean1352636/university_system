# REST API Reference

The University Management System exposes a comprehensive REST API via Flask. All endpoints are prefixed with `/api/` unless otherwise noted.

## Base URL

```
http://localhost:5000/api
```

Configure the host and port in `university_system/data/config/api_config.json`.

## Authentication

The API uses **JWT Bearer tokens** for authentication.

### Login Flow

```
POST /api/auth/login
Content-Type: application/json

{
  "username": "student001",
  "password": "your_password"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": 1, "username": "student001", "role": "student" }
}
```

### Using the Token

Include the token in the `Authorization` header for all subsequent requests:

```
Authorization: Bearer eyJ...
```

### Refreshing Tokens

```
POST /api/auth/refresh
Authorization: Bearer <current_token>
```

## Common Patterns

### Pagination

Most list endpoints support pagination:

```
GET /api/students?page=1&per_page=20
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
GET /api/courses?department=CS&level=300&search=algorithms
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
| `/api/auth` | Login, logout, token refresh, current user info |
| `/api/users` | User account management (admin-gated) |

### Academic Core

| Prefix | Description |
|---|---|
| `/api/courses` | Course catalog, CRUD, and waitlist management |
| `/api/students` | Student profiles and record management |
| `/api/grades` | Grade recording, updates, and transcripts |
| `/api/attendance` | Session tracking and attendance records |
| `/api/assignments` | Assignment CRUD, submissions, and grading |
| `/api/assessments` | Module assessments and evaluations |
| `/api/exams` | Exam scheduling and accommodations |
| `/api/modules` | Course/subject creation, updates, and management |
| `/api/timetable` | Module schedules and student timetables |
| `/api/evaluations` | Course evaluations and feedback submissions |

### Finance

| Prefix | Description |
|---|---|
| `/api/finance` | Fees, payments, and account balances |
| `/api/financial-aid` | Aid applications, packages, and payment plans |
| `/api/scholarships` | Scholarship listings and applications |

### Student Life

| Prefix | Description |
|---|---|
| `/api/clubs` | Student club management and memberships |
| `/api/events` | Campus event creation and registrations |
| `/api/elections` | Polls, candidates, votes, and union representatives |
| `/api/study-groups` | Study group creation and memberships |
| `/api/mentorship` | Mentor relationships and session tracking |
| `/api/dining` | Meal accounts, transactions, and menu items |
| `/api/lost-found` | Lost item reporting and claims |
| `/api/equipment` | Equipment checkouts, rentals, and maintenance |

### Campus & Facilities

| Prefix | Description |
|---|---|
| `/api/campus` | Buildings, rooms, tours, and resource bookings |
| `/api/housing` | Accommodation applications and room assignments |
| `/api/accommodations` | Disability and accessibility services |
| `/api/parking` | Parking permits, spaces, and vehicles |
| `/api/facilities` | Facility booking and maintenance requests |
| `/api/security` | Security desk tickets and incident management |
| `/api/emergency` | Emergency alerts, contacts, and incidents |

### Health & Counseling

| Prefix | Description |
|---|---|
| `/api/health-services` | Medical appointments and health records |
| `/api/counseling` | Mental health appointments and crisis resources |

### Career & Alumni

| Prefix | Description |
|---|---|
| `/api/career` | Job postings, applications, and internships |
| `/api/alumni` | Alumni profiles, events, and donations |
| `/api/advising` | Academic advising appointments |

### Support & Communication

| Prefix | Description |
|---|---|
| `/api/helpdesk` | Support tickets, KB articles, and FAQs |
| `/api/notifications` | Notification management and preferences |
| `/api/announcements` | Campus-wide announcements |
| `/api/communication` | Messages, emails, newsletters, and SMS |
| `/api/chat` | Messaging rooms and direct messages |

### Administration

| Prefix | Description |
|---|---|
| `/api/dashboard` | Aggregate statistics and analytics |
| `/api/hr` | Staff, departments, leave, shifts, timesheets, and appraisals |
| `/api/documents` | Document management and workflows |
| `/api/credentials` | Blockchain credentials, badges, and certifications |
| `/api/degrees` | Degree programs, requirements, and prerequisites |

### Academic Services

| Prefix | Description |
|---|---|
| `/api/admissions` | Prospect management and admission applications |
| `/api/enrollments` | Course enrollment and module registration |
| `/api/library` | Book catalog, loans, and reservations |
| `/api/integrity` | Academic misconduct cases, plagiarism, and AI detection |
| `/api/lms` | Learning management: courses, quizzes, forums, gradebook |
| `/api/virtual-classrooms` | Virtual classrooms, sessions, and recordings |
| `/api/office-hours` | Office hour scheduling and booking |
| `/api/teaching-assistants` | TA assignments and permissions |
| `/api/tutoring` | Peer tutoring offers |
| `/api/early-warning` | Student risk profiles and interventions |
| `/api/parents` | Parent portal accounts and student links |
| `/api/research` | Research projects and publications |
| `/api/calendar` | Academic calendar and events |

### System

| Prefix | Description |
|---|---|
| `/` | Health check (`GET /`) and API version info (`GET /api`) |

---

## Running the API Server

```bash
# Start the development server
python -m university_system.api.api_server

# Or via make
make run-api
```

The server starts on `http://localhost:5000` by default. Configuration is loaded from `university_system/data/config/api_config.json`.

## CORS

Cross-Origin Resource Sharing is configured via the `CORS_ALLOWED_ORIGINS` environment variable (comma-separated list of origins). Defaults to `http://localhost:3000`.

```bash
export CORS_ALLOWED_ORIGINS="http://localhost:3000,https://your-frontend.example.com"
```
