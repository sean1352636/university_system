# REST API Reference

The Education System provides a unified REST API server that serves all seven systems from a single Flask application. Routes live in `src/education_system/api/<system>/`; the mount table is `src/education_system/platform/delivery/api/registry.py` and the server is `src/education_system/platform/delivery/api/unified_server.py`.

## Starting the API Server

```bash
python -m education_system --api
```

Or directly:
```bash
python -m education_system.platform.delivery.api.unified_server
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Listen address |
| `API_PORT` | `5000` | Listen port |
| `API_DEBUG` | `false` | Flask debug mode |
| `JWT_SECRET_KEY` | required in production | HMAC secret for JWT signing; outside production one is generated and stored in `auth.db` |
| `JWT_EXPIRY_HOURS` | `24` | Access token lifetime |
| `JWT_REFRESH_DAYS` | `7` | Refresh token lifetime |
| `API_CORS_ORIGINS` | required in production | Comma-separated allowed origins; outside production, localhost only |
| `LOG_LEVEL` | `INFO` | Logging level |

## Base URLs

```
/api/v1/auth/*         Shared authentication
/api/v1/health         Health check
/api/v1/university/*   University routes
/api/v1/sixthform/*    Sixth Form College routes
/api/v1/school/*       Secondary School routes
/api/v1/primary/*      Primary School routes
/api/v1/nursery/*      Nursery / Early Years routes
/api/v1/fecollege/*    FE College routes
/api/v1/apprentice/*   Apprenticeships routes
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
  "message": "Login successful.",
  "token": "eyJ...",
  "refresh_token": "...",
  "user": {
    "user_id": 1,
    "username": "admin",
    "display_name": "Administrator",
    "systems": [
      {"system_key": "university", "role": "admin"}
    ],
    "password_expired": false,
    "must_change_password": false
  }
}
```

If MFA is enabled the response instead carries `"mfa_required": true` and an `mfa_token`; send that token and the code to `POST /api/v1/auth/mfa/verify`.

### Using Tokens

Include the `token` value in the `Authorization` header:

```
Authorization: Bearer eyJ...
```

### Token Refresh

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "..."
}
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

## University System Endpoints

Route modules live in `src/education_system/api/university/<area>/`; campus commerce routes are in `src/education_system/systems/university/plugins/campus_commerce/api/`.

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
| `/api/v1/university/timetable` | Schedules, student timetables |
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
| `/api/v1/university/hr` | Staff, departments, leave |
| `/api/v1/university/helpdesk` | Support tickets, FAQs |
| `/api/v1/university/email` | Email |
| `/api/v1/university/mail` | Mail |
| `/api/v1/university/alumni` | Alumni profiles, events |
| `/api/v1/university/admissions` | Applications, prospects |
| `/api/v1/university/integrity` | Academic misconduct |
| `/api/v1/university/research` | Research projects |
| `/api/v1/university/credentials` | Credential issue and verification |
| `/api/v1/university/blockchain` | Blockchain badges |

Further university prefixes include `absence`, `academic-progress`, `academics`, `accessibility`, `accommodations`, `achievement-badges`, `admissions-crm`, `admissions-references`, `admissions/ucas`, `advising`, `ai`, `ai-study`, `analytics`, `budget`, `calendar`, `campus-navigation`, `clearing-adjustment`, `collaborative-provision`, `commerce`, `course-planning`, `degrees`, `early-warning`, `external-examiners`, `feedback`, `graduation`, `hesa-export`, `legal`, `mobility`, `office-hours`, `operations`, `parents`, `portfolio`, `roommate-finder`, `scholarship-finder`, `social-matching`, `staff-hr`, `student-affairs`, `student-app`, `student-finance`, `student-id`, `student-jobs`, `student-lifecycle`, `student-mobility`, `student-wellbeing`, `study-matching`, `study-recommendations`, `study-rooms`, `teaching-assistants`, `textbooks`, `tutoring`, `virtual-classrooms`, `wellness`, and the commerce shops (`barber`, `betting`, `butcher`, `carrental`, `cinema`, `gym`, `marketplace`, `musicshop`, `nailbar`, `phoneshop`, `printing`).

Learning-management sync is a platform route (`/api/v1/lms`), not a university one.

### Standard CRUD Pattern

Most resource endpoints follow this pattern:

```
GET    /api/v1/{system}/{resource}           List (paginated)
POST   /api/v1/{system}/{resource}           Create
GET    /api/v1/{system}/{resource}/{id}      Get by ID
PUT    /api/v1/{system}/{resource}/{id}      Update
DELETE /api/v1/{system}/{resource}/{id}      Delete
```

## Sixth Form College Endpoints (`/api/v1/sixthform`)

Key route groups: `academic-year`, `academics`, `applicant-portal`, `applications`, `assessment`, `calendar`, `finance`, `governance`, `onboarding`, `pastoral`, `progression`, `reports`, `staff-comms`, `student-services`, and main-menu routes under `menu/`.

## Secondary School Endpoints (`/api/v1/school`)

Key route groups: `pupils`, `academics`, `assessment`, `finance`, `governance`, `pastoral`, `reports`, `staff-comms`, and main-menu routes under `menu/`.

## Primary School Endpoints (`/api/v1/primary`)

One blueprint per module. Key route groups: `pupils`, `subjects`, `classes`, `assessment`, `attendance`, `timetable`, `homework`, `ks1-sats`, `ks2-sats`, `phonics`, `phonics-screening`, `reading-levels`, `safeguarding`, `send`, `admissions`, `library`, `dinner-money`, `transport`, `clubs`, and main-menu routes under `menu/`.

## Nursery / Early Years Endpoints (`/api/v1/nursery`)

One blueprint per module. Key route groups: `children`, `admissions`, `enrolment`, `daily-diary`, `daily-register`, `development-tracking`, `curriculum-planning`, `allergies`, `accident-log`, `dsl`, `ehc-plans`, `emergency-contacts`, and more.

## FE College Endpoints (`/api/v1/fecollege`)

Main-menu routes only, under `menu/` (`overview`, `people`, `curriculum`, `money`, `communication`, `teaching`, `assessment`, `learners`, `my-learning`, `me`, `account`). Each answers 501 until it is backed by a service; the resource modules beside them are empty.

## Apprenticeships Endpoints (`/api/v1/apprentice`)

Main-menu routes only, under `menu/` (`overview`, `people`, `approvals`, `delivery`, `assessment`, `assurance`, `communication`, `feedback`, `finishing`, `my-apprenticeship`, `my-evidence`). Each answers 501 until it is backed by a service; the resource modules beside them are empty.

## Error Response Format

Errors raised through the app's handlers use RFC 7807 `application/problem+json` (`platform/delivery/api/kernel/problems.py`), with a legacy `error` key alongside it:

```json
{
  "type": "https://education-system.invalid/problems/forbidden",
  "title": "Forbidden",
  "status": 403,
  "detail": "You may not access this resource.",
  "instance": "/api/v1/university/students/42",
  "trace_id": "36739411e33e4f25"
}
```

Auth routes return a plain `{"error": "..."}` body.

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
