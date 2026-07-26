# College System -- REST API Reference

This document describes the Flask REST API for the Sixth Form College Management System.

---

## Table of Contents

1. [Server Setup](#server-setup)
2. [Authentication](#authentication)
3. [Error Handling](#error-handling)
4. [Pagination](#pagination)
5. [Input Validation](#input-validation)
6. [API Endpoints](#api-endpoints)

---

## Server Setup

The API uses a Flask **app factory** pattern defined in `api/api_server.py`:

```python
def create_app(db_path: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)
    init_db(db_path)
    seed_default_data(db_path)

    for init_func in ALL_INIT_FUNCS:
        init_func(db_path)

    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    register_error_handlers(app)
    return app
```

**Starting the server:**

```bash
python run.py --college --api
```

Default: `http://127.0.0.1:5000`. CORS is enabled for all origins.

**Configuration** (`api/config.py`):

| Setting            | Default             | Description                 |
|--------------------|---------------------|-----------------------------|
| `JWT_SECRET_KEY`   | From `core/defaults`| Secret for signing JWTs     |
| `JWT_EXPIRY_HOURS` | `24`                | Token lifetime in hours     |
| `DEBUG`            | From `core/defaults`| Flask debug mode            |
| `JSON_SORT_KEYS`   | `False`             | Preserve dict key order     |


## Authentication

Authentication is handled via **JWT bearer tokens** (`api/auth.py`).

### Login Flow

1. POST credentials to `/api/auth/login`.
2. If MFA is not enabled, the response includes a `token`.
3. If MFA is enabled, the response includes `mfa_required: true` and a short-lived `mfa_token` (5-minute expiry). Complete MFA verification via `/api/mfa/verify` to receive the full JWT.

### Token Structure

The JWT payload contains:

```json
{
  "user_id": 1,
  "username": "admin",
  "role": "admin",
  "exp": 1709942400,
  "iat": 1709856000
}
```

### Using Tokens

Include the token in the `Authorization` header:

```
Authorization: Bearer <token>
```

### Decorators

| Decorator                  | Purpose                                            |
|----------------------------|----------------------------------------------------|
| `@token_required`          | Requires a valid JWT; populates `g.current_user`   |
| `@role_required(*roles)`   | Requires the user's role to be in the given list   |
| `@mfa_token_required`      | Requires a valid short-lived MFA verification token|

Roles used throughout the system: `admin`, `staff`, `instructor`, `student`.

### Example: Obtain a Token

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "Admin@123"}'
```

Response:

```json
{
  "message": "Login successful.",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "user_id": 1,
    "username": "admin",
    "role": "admin"
  }
}
```


## Error Handling

All errors are returned as JSON with a consistent structure:

```json
{
  "error": "Error Type",
  "message": "Human-readable description."
}
```

### HTTP Status Code Mapping

| Exception            | Status Code |
|----------------------|-------------|
| `ValidationError`    | 400         |
| Domain errors (e.g., `StudentError`, `CourseError`) | 400 |
| `AuthError`          | 401         |
| Not found            | 404         |
| Method not allowed   | 405         |
| `DatabaseError`      | 500         |
| `CollegeSystemError` | 500         |
| Unhandled exceptions | 500         |


## Pagination

List endpoints support pagination via query parameters. The helpers are in `api/pagination.py`.

### Query Parameters

| Parameter  | Default | Range    | Description                |
|------------|---------|----------|----------------------------|
| `page`     | `1`     | >= 1     | Page number                |
| `per_page` | `20`    | 1 -- 100 | Items per page             |

### Response Envelope

All paginated responses use this envelope:

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8,
    "has_next": true,
    "has_prev": false
  }
}
```

### Example

```bash
curl http://localhost:5000/api/students?page=2&per_page=10 \
  -H "Authorization: Bearer <token>"
```


## Input Validation

Request validation helpers are in `api/validators.py`.

### `get_json_body()`

Extracts and validates that the request body is valid JSON. Raises `ValidationError` (HTTP 400) if the body is missing or malformed.

### `require_fields(data, *fields)`

Checks that all named fields are present and non-null in the data dict. Raises `ValidationError` with a message listing the missing fields.

Example usage in a route:

```python
data = get_json_body()
require_fields(data, "first_name", "last_name")
```


## API Endpoints

All endpoints are prefixed with `/api/`. Unless noted otherwise, all endpoints except `/api/auth/login` and `/api/auth/register` require a valid JWT token via `@token_required`. Endpoints that create, update, or delete records additionally require `@role_required("admin")` or `@role_required("admin", "staff")`.

### Standard CRUD Pattern

Most domain modules follow a consistent pattern:

```
GET    /api/<resource>                List (paginated)
GET    /api/<resource>/<id>           Get by primary key
POST   /api/<resource>               Create (admin/staff)
PUT    /api/<resource>/<id>           Update (admin/staff)
DELETE /api/<resource>/<id>           Delete (admin only)
```

Successful responses:
- **GET list**: `200` with paginated envelope
- **GET single**: `200` with `{"data": {...}}`
- **POST create**: `201` with `{"message": "...", "data": {...}}`
- **PUT update**: `200` with `{"message": "...", "data": {...}}`
- **DELETE**: `200` with `{"message": "..."}`

### Example: Full CRUD on Students

```bash
# List students (paginated)
curl http://localhost:5000/api/students?page=1&per_page=20 \
  -H "Authorization: Bearer $TOKEN"

# Get a single student
curl http://localhost:5000/api/students/1 \
  -H "Authorization: Bearer $TOKEN"

# Create a student
curl -X POST http://localhost:5000/api/students \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name": "Alice", "last_name": "Smith", "year_group": "12", "form_group": "12A"}'

# Update a student
curl -X PUT http://localhost:5000/api/students/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"year_group": "13"}'

# Delete a student
curl -X DELETE http://localhost:5000/api/students/1 \
  -H "Authorization: Bearer $TOKEN"
```

---

### Route File Reference

Below are all 59 route modules grouped by category. Each route file creates a Flask Blueprint with the indicated URL prefix.

#### Authentication and Security

| Route File                   | URL Prefix           | Key Endpoints                                      |
|------------------------------|----------------------|----------------------------------------------------|
| `auth_routes.py`             | `/api/auth`          | POST `/login`, POST `/register`, GET `/me`, POST `/change-password` |
| `mfa_routes.py`              | `/api/mfa`           | MFA setup, verify, recovery codes                  |
| `user_management_routes.py`  | `/api/user-management` | User CRUD, role management, account status        |
| `gdpr_routes.py`             | `/api/gdpr`          | Data subject requests, consent records, data export|

#### Students and Learner Records

| Route File                   | URL Prefix                | Key Endpoints                               |
|------------------------------|---------------------------|---------------------------------------------|
| `student_routes.py`          | `/api/students`           | CRUD, GET `/by-id/<student_id>`, GET `/<id>/profile` |
| `enrollment_routes.py`       | `/api/enrollments`        | POST `/enroll`, POST `/drop`, GET `/student/<id>`, GET `/course/<id>` |
| `grade_routes.py`            | `/api/grades`             | POST `/record`, GET `/student/<id>`, GET `/student/<id>/ucas-points` |
| `attendance_routes.py`       | `/api/attendance`         | POST `/sessions`, POST `/record`, GET `/student/<id>`, GET `/course/<id>` |
| `student_support_routes.py`  | `/api/student-support`    | Support plans, referrals, notes             |
| `intervention_tracking_routes.py` | `/api/interventions` | Intervention CRUD, progress tracking        |
| `progress_dashboard_routes.py` | `/api/progress-dashboard` | Student progress summaries, risk flags    |

#### Courses and Teaching

| Route File                   | URL Prefix             | Key Endpoints                                |
|------------------------------|------------------------|----------------------------------------------|
| `course_routes.py`           | `/api/courses`         | CRUD, GET `/by-code/<code>`, GET `/<id>/roster`, GET/POST `/<id>/prerequisites` |
| `assignment_routes.py`       | `/api/assignments`     | Assignment CRUD, submissions                 |
| `timetable_routes.py`        | `/api/timetable`       | Timetable slots, student/instructor schedules|
| `room_routes.py`             | `/api/rooms`           | Room CRUD, availability checks               |
| `markbook_routes.py`         | `/api/markbook`        | Assessment marks, component tracking         |
| `lesson_plans_routes.py`     | `/api/lesson-plans`    | Lesson plan CRUD, sharing                    |

#### Staff and HR

| Route File                   | URL Prefix              | Key Endpoints                              |
|------------------------------|-------------------------|--------------------------------------------|
| `cpd_routes.py`              | `/api/cpd`              | CPD record CRUD, training events           |
| `observations_routes.py`     | `/api/observations`     | Teaching observation CRUD, feedback        |
| `appraisals_routes.py`       | `/api/appraisals`       | Appraisal CRUD, objectives, reviews        |
| `staff_wellbeing_routes.py`  | `/api/staff-wellbeing`  | Wellbeing check-ins, surveys               |
| `absence_requests_routes.py` | `/api/absence-requests` | Staff absence request CRUD, approvals      |

#### Departments and Groups

| Route File                   | URL Prefix            | Key Endpoints                               |
|------------------------------|-----------------------|---------------------------------------------|
| `department_routes.py`       | `/api/departments`    | Department CRUD, staff assignment            |
| `group_routes.py`            | `/api/groups`         | Student group CRUD, membership               |

#### Finance and Funding

| Route File                   | URL Prefix          | Key Endpoints                                 |
|------------------------------|---------------------|-----------------------------------------------|
| `finance_routes.py`          | `/api/finance`      | Invoices, payments, fee management             |
| `funding_routes.py`          | `/api/funding`      | ILR records, funding allocations               |

#### Destinations and Careers

| Route File                   | URL Prefix           | Key Endpoints                               |
|------------------------------|----------------------|---------------------------------------------|
| `destination_routes.py`      | `/api/destinations`  | Destination tracking, outcomes               |

#### Student Experience

| Route File                      | URL Prefix                 | Key Endpoints                         |
|---------------------------------|----------------------------|---------------------------------------|
| `enrichment_routes.py`          | `/api/enrichment`          | Enrichment activity CRUD, enrolment   |
| `peer_mentoring_routes.py`      | `/api/peer-mentoring`      | Mentoring pair CRUD, session logging  |
| `portfolio_routes.py`           | `/api/portfolio`           | Student portfolio CRUD, artefacts     |
| `study_planner_routes.py`       | `/api/study-planner`       | Study session CRUD, goals             |
| `skills_passport_routes.py`     | `/api/skills-passport`     | Skill records, endorsements           |
| `work_journal_routes.py`        | `/api/work-journal`        | Work experience journal entries       |
| `meal_ordering_routes.py`       | `/api/meal-ordering`       | Meal menu, orders, dietary prefs      |
| `print_credits_routes.py`       | `/api/print-credits`       | Print credit balances, transactions   |
| `surveys_routes.py`             | `/api/surveys`             | Survey CRUD, questions, responses     |

#### Administration and Compliance

| Route File                       | URL Prefix                  | Key Endpoints                       |
|----------------------------------|-----------------------------|-------------------------------------|
| `academic_year_routes.py`        | `/api/academic-year`        | Academic year CRUD, term dates      |
| `policies_routes.py`             | `/api/policies`             | Policy CRUD, acknowledgements       |
| `quality_assurance_routes.py`    | `/api/quality-assurance`    | QA reviews, action plans            |
| `audit_reports_routes.py`        | `/api/audit-reports`        | Audit report generation, history    |
| `bulk_operations_routes.py`      | `/api/bulk-operations`      | Bulk create/update/delete           |
| `visitors_routes.py`             | `/api/visitors`             | Visitor sign-in/out, pre-registration |
| `emergency_routes.py`            | `/api/emergency`            | Emergency contacts, drills, alerts  |
| `resource_booking_routes.py`     | `/api/resource-booking`     | Resource CRUD, booking slots        |

#### Communication and Notifications

| Route File                       | URL Prefix                 | Key Endpoints                        |
|----------------------------------|----------------------------|--------------------------------------|
| `notification_routes.py`         | `/api/notifications`       | Notification list, mark read         |
| `announcements_routes.py`        | `/api/announcements`       | Announcement CRUD, targeting         |
| `sms_email_routes.py`            | `/api/sms-email`           | Send SMS/email, templates, logs      |
| `feedback_routes.py`             | `/api/feedback`            | Feedback submissions, responses      |
| `activity_feed_routes.py`        | `/api/activity-feed`       | Activity stream, filters             |

#### Dashboards and Analytics

| Route File                       | URL Prefix                  | Key Endpoints                       |
|----------------------------------|-----------------------------|-------------------------------------|
| `data_dashboard_routes.py`       | `/api/data-dashboard`       | Dashboard widgets, metrics          |
| `kpi_dashboard_routes.py`        | `/api/kpi`                  | KPI definitions, current values     |
| `mobile_dashboard_routes.py`     | `/api/mobile-dashboard`     | Mobile-optimised summary endpoints  |

#### Documents and Search

| Route File                       | URL Prefix                  | Key Endpoints                       |
|----------------------------------|-----------------------------|-------------------------------------|
| `document_hub_routes.py`         | `/api/document-hub`         | Document upload, download, metadata |
| `attachments_routes.py`          | `/api/attachments`          | File attachment CRUD                |
| `advanced_search_routes.py`      | `/api/advanced-search`      | Cross-module search                 |

#### Accessibility and Localisation

| Route File                       | URL Prefix                  | Key Endpoints                       |
|----------------------------------|-----------------------------|-------------------------------------|
| `accessibility_routes.py`        | `/api/accessibility`        | Accessibility preference CRUD       |
| `multi_language_routes.py`       | `/api/multi-language`       | Language preference, translations   |

#### System

| Route File                       | URL Prefix          | Key Endpoints                               |
|----------------------------------|---------------------|---------------------------------------------|
| `system_routes.py`               | `/api/system`       | GET `/health`, GET `/version`, GET `/stats`  |
