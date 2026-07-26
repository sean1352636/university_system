# REST API Reference

The Education System provides a unified REST API server that serves all four subsystems from a single Flask application.

## Starting the API Server

```bash
python run.py --api
```

Or directly:
```bash
python -m education_system.shared.api.unified_server
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Listen address |
| `API_PORT` | `5000` | Listen port |
| `API_DEBUG` | `false` | Flask debug mode |
| `JWT_SECRET_KEY` | auto-generated | HMAC secret for JWT signing |
| `JWT_EXPIRY_HOURS` | `24` | Access token lifetime |
| `JWT_REFRESH_DAYS` | `7` | Refresh token lifetime |
| `API_CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Logging level |

## Base URLs

```
/api/v1/auth/*         Shared authentication
/api/v1/health         Health check
/api/v1/university/*   University routes
/api/v1/college/*      College routes
/api/v1/school/*       Secondary School routes
/api/v1/primary/*      Primary School routes
/api/v1/docs           Swagger UI / OpenAPI
/api/v1/webhooks       Webhook management
```

The index endpoint (`GET /api/v1`) returns a JSON listing of all available endpoints.

## Authentication

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "systems": [
      {"system_key": "university", "role": "admin"}
    ]
  }
}
```

### Using Tokens

Include the access token in the `Authorization` header:

```
Authorization: Bearer eyJ...
```

### Token Refresh

```http
POST /api/v1/auth/refresh
Authorization: Bearer <refresh_token>
```

### Other Auth Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/auth/me` | Current user info |
| `POST` | `/api/v1/auth/change-password` | Change password |
| `POST` | `/api/v1/auth/mfa/verify` | Complete MFA challenge |
| `POST` | `/api/v1/auth/logout` | Revoke refresh token |

### Rate Limiting

- Login: 10 attempts per IP per 60 seconds, 5 per username per 60 seconds
- Registration: 5 per hour per IP

## University System Endpoints (52 route modules)

### Academic Core

| Prefix | Description |
|--------|-------------|
| `/api/v1/university/students` | Student profiles, enrollment, records |
| `/api/v1/university/courses` | Course catalog, CRUD, waitlists |
| `/api/v1/university/modules` | Course/subject management |
| `/api/v1/university/enrollments` | Course enrollment, registration |
| `/api/v1/university/grades` | Grade recording, transcripts |
| `/api/v1/university/attendance` | Session tracking, records |
| `/api/v1/university/assignments` | Assignment CRUD, submissions, grading |
| `/api/v1/university/assessments` | Module assessments |
| `/api/v1/university/exams` | Exam scheduling, accommodations |
| `/api/v1/university/timetables` | Schedules, student timetables |
| `/api/v1/university/evaluations` | Course evaluations |

### Finance

| Prefix | Description |
|--------|-------------|
| `/api/v1/university/finance` | Fees, payments, balances |
| `/api/v1/university/financial-aid` | Aid applications, packages |
| `/api/v1/university/scholarships` | Scholarship listings |

### Student Life

| Prefix | Description |
|--------|-------------|
| `/api/v1/university/clubs` | Student clubs, memberships |
| `/api/v1/university/events` | Campus events |
| `/api/v1/university/elections` | Student union elections |
| `/api/v1/university/study-groups` | Study group management |
| `/api/v1/university/mentorship` | Mentor relationships |
| `/api/v1/university/dining` | Meal accounts, menus |
| `/api/v1/university/lost-found` | Lost item reporting |
| `/api/v1/university/equipment` | Equipment rentals |
| `/api/v1/university/health-services` | Medical appointments |
| `/api/v1/university/counseling` | Mental health services |
| `/api/v1/university/career` | Job postings, internships |

### Campus & Facilities

| Prefix | Description |
|--------|-------------|
| `/api/v1/university/campus` | Buildings, rooms, tours |
| `/api/v1/university/housing` | Accommodation, room assignments |
| `/api/v1/university/parking` | Permits, spaces |
| `/api/v1/university/facilities` | Booking, maintenance |
| `/api/v1/university/security` | Incident management |
| `/api/v1/university/emergency` | Emergency alerts |
| `/api/v1/university/library` | Catalog, loans, reservations |

### Administration

| Prefix | Description |
|--------|-------------|
| `/api/v1/university/dashboard` | Aggregate statistics |
| `/api/v1/university/hr` | Staff, departments, leave |
| `/api/v1/university/helpdesk` | Support tickets, FAQs |
| `/api/v1/university/notifications` | Notification management |
| `/api/v1/university/announcements` | Campus announcements |
| `/api/v1/university/communication` | Messages, emails, SMS |
| `/api/v1/university/alumni` | Alumni profiles, events |
| `/api/v1/university/admissions` | Applications, prospects |
| `/api/v1/university/integrity` | Academic misconduct |
| `/api/v1/university/lms` | Learning management |
| `/api/v1/university/research` | Research projects |
| `/api/v1/university/credentials` | Blockchain badges |

### Standard CRUD Pattern

Most resource endpoints follow this pattern:

```
GET    /api/v1/{system}/{resource}           List (paginated)
POST   /api/v1/{system}/{resource}           Create
GET    /api/v1/{system}/{resource}/{id}      Get by ID
PUT    /api/v1/{system}/{resource}/{id}      Update
DELETE /api/v1/{system}/{resource}/{id}      Delete
```

## College System Endpoints (58 route modules)

Key route groups: `students`, `courses`, `enrollments`, `grades`, `attendance`, `assignments`, `exams`, `timetables`, `staff`, `departments`, `finance`, `ucas`, `tlevel`, `study-programmes`, `functional-skills`, `safeguarding`, `send`, `pastoral`, `behaviour`, `careers`, `alumni`, `library`, `transport`, `meals`, and 30+ more.

## Secondary School Endpoints (40 route modules)

Key route groups: `students`, `subjects`, `enrollments`, `grades`, `attendance`, `behaviour`, `exams`, `homework`, `timetables`, `pastoral`, `safeguarding`, `send`, `staff`, `admissions`, `finance`, `library`, `meals`, `transport`, `clubs`, and 20+ more.

## Primary School Endpoints (46 route modules)

Key route groups: `pupils`, `subjects`, `classes`, `assessments`, `attendance`, `timetables`, `homework`, `sats`, `phonics`, `reading-records`, `safeguarding`, `send`, `pastoral`, `admissions`, `finance`, `library`, `meals`, `transport`, `clubs`, and 25+ more.

## Error Response Format

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "status": 400
}
```

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request / validation error |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not found |
| 422 | Validation error (payload) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

## Security

- CSRF protection (Origin/Referer validation)
- Security headers: X-Frame-Options, X-Content-Type-Options, CSP, HSTS
- HTTPS enforcement in production
- HttpOnly, Secure, SameSite cookies
- Request logging with structured JSON output
