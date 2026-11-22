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

Route blueprints live in `src/education_system/api/sixth_form/routes/`, and the unified server in `src/education_system/platform/delivery/api/unified_server.py` hosts them with those of the other six systems. `platform/delivery/api/registry.py` is the mount table.

**Starting the server:**

```bash
python -m education_system --college --api
```

Default: port `5000`. The sixth form is mounted at `/api/v1/sixthform`: a blueprint's `/api/<resource>` prefix becomes `/api/v1/sixthform/<resource>`. CORS allows only the origins in `API_CORS_ORIGINS`, which production must set; development falls back to localhost.

**Configuration** (environment variables):

| Setting            | Default             | Description                 |
|--------------------|---------------------|-----------------------------|
| `API_PORT`         | `5000`              | Server port                 |
| `JWT_SECRET_KEY`   | None                | Secret for signing JWTs; required in production |
| `JWT_EXPIRY_HOURS` | `24`                | Token lifetime in hours     |
| `JWT_REFRESH_DAYS` | `7`                 | Refresh token lifetime in days |
| `API_CORS_ORIGINS` | None                | Comma-separated allowed origins |

**Standalone server:** `python -m education_system.api.sixth_form.server` runs a separate, smaller app (`create_app` in `src/education_system/api/sixth_form/server.py`) with the parent portal under `/api/parent/*`, signed by `api/sixth_form/tokens.py`, and staff endpoints that take an `X-API-Key` header matching `EDU_SIXTHFORM_API_KEY`. The rest of this document describes the unified server.


## Authentication

Authentication is handled via **JWT bearer tokens**, shared by all systems (`src/education_system/platform/delivery/api/security/authentication.py`, with handlers in `platform/delivery/api/routes/auth_routes.py`).

### Login Flow

1. POST credentials to `/api/v1/auth/login`.
2. If MFA is not enabled, the response includes a `token` and a `refresh_token`.
3. If MFA is enabled, the response includes `mfa_required: true` and a short-lived `mfa_token` (5-minute expiry). Complete MFA verification via `/api/v1/auth/mfa/verify` to receive the full JWT.

### Token Structure

The JWT payload contains:

```json
{
  "user_id": 1,
  "username": "admin1",
  "systems": [{"system_key": "sixth_form", "role": "admin"}],
  "type": "access",
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
| `@token_required`          | Requires a valid JWT and an active account; populates `g.current_user`, with the role taken from the system in the request path |
| `@role_required(*roles)`   | Requires the user's role to be in the given list   |
| `@system_required(key)`    | Requires access to the named system                |

Sixth form routes add a capability check. Each route module wraps its views in `access_gate.gate` (`src/education_system/api/sixth_form/access_gate.py`), which resolves the caller's capabilities and applies the read or write rule for the route. A route without a rule is refused.

Roles used in the sixth form: `admin`, `staff`, `teacher`, `student`, `parent`.

### Example: Obtain a Token

```bash
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin1", "password": "admin1234"}'
```

Response:

```json
{
  "message": "Login successful.",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "user_id": 1,
    "username": "admin1",
    "display_name": "admin1",
    "systems": [{"system_key": "sixth_form", "role": "admin"}],
    "password_expired": false,
    "must_change_password": false
  }
}
```


## Error Handling

Sixth form routes return errors as JSON with an `error` message:

```json
{
  "error": "Human-readable description."
}
```

### HTTP Status Code Mapping

| Case                 | Status Code |
|----------------------|-------------|
| A domain module's `ValidationError` | 400 |
| Missing, expired or invalid token | 401 |
| Capability or system access refused | 403 |
| Not found            | 404         |
| Method not allowed   | 405         |
| Rate limited         | 429         |
| Unhandled exceptions | 500         |

Common handlers are in `src/education_system/platform/delivery/api/errors.py`.


## Pagination

Sixth form list endpoints return the rows under the resource name with a count, such as `{"courses": [...], "count": n}`, and most take filters rather than page parameters. For a new endpoint that needs paging, the shared helpers are in `src/education_system/platform/delivery/api/kernel/pagination.py`.

### Query Parameters

| Parameter  | Default | Range    | Description                |
|------------|---------|----------|----------------------------|
| `page`     | `1`     | >= 1     | Page number                |
| `per_page` | `20`    | 1 -- 100 | Items per page             |


## Input Validation

Domain modules validate their own payloads and raise their own `ValidationError`, which the route turns into a 400. Shared request helpers for new code are in `src/education_system/platform/delivery/api/validators.py`.

### `get_json_body()`

Extracts and validates that the request body is valid JSON. Raises a validation error (HTTP 400) if the body is missing or malformed.

### `require_fields(data, *fields)`

Checks that all named fields are present and non-null in the data dict. Raises a validation error listing the missing fields.

Example usage in a route:

```python
data = get_json_body()
require_fields(data, "first_name", "last_name")
```


## API Endpoints

All sixth form endpoints are prefixed with `/api/v1/sixthform/`. Unless noted otherwise, they require a valid JWT, and pass through the capability check. Authentication endpoints are shared, at `/api/v1/auth/`.

### Standard CRUD Pattern

Most domain resources follow a consistent pattern:

```
GET    /api/v1/sixthform/<area>/<resource>                List
GET    /api/v1/sixthform/<area>/<resource>/<id>           Get by primary key
POST   /api/v1/sixthform/<area>/<resource>                Create
PUT    /api/v1/sixthform/<area>/<resource>/<id>           Update
DELETE /api/v1/sixthform/<area>/<resource>/<id>           Delete
```

Successful responses:
- **GET list**: `200` with `{"<resource>": [...], "count": n}`
- **GET single**: `200` with the record
- **POST create**: `201` with the record
- **PUT update**: `200` with the record
- **DELETE**: `200` with `{"deleted": <id>}`

### Example: Courses

```bash
BASE=http://localhost:5000/api/v1/sixthform

# List courses
curl $BASE/academics/courses \
  -H "Authorization: Bearer $TOKEN"

# Get a single course
curl $BASE/academics/courses/1 \
  -H "Authorization: Bearer $TOKEN"

# Delete a course
curl -X DELETE $BASE/academics/courses/1 \
  -H "Authorization: Bearer $TOKEN"
```

---

### Route File Reference

Below are the route modules in `src/education_system/api/sixth_form/routes/`. Each creates a Flask Blueprint, and prefixes are shown after mounting, relative to `/api/v1/sixthform`.

| Route File | URL Prefix | Resources |
|------------|------------|-----------|
| `academic_year_routes.py` | `/academic-year` | `/current`, `/summary`, `/lookup`, `/import`, `/webhooks`, `/calendar.ics` |
| `academics_routes.py` | `/academics` | `/courses`, `/subjects` |
| `advanced_search_routes.py` | `/` | `/advanced-search` |
| `applicant_portal_routes.py` | `/applicant-portal` | `/code`, `/session`, `/status`, `/offer`, `/documents`, `/contact` |
| `applications_routes.py` | `/applications` | Collection root |
| `assessment_routes.py` | `/assessment` | `/predicted-grades`, `/targets`, `/reviews`, `/gradebook` |
| `calendar_routes.py` | `/calendar` | `/status`, `/day`, `/week`, `/summary`, `/bookings`, `/portal`, `/feed.ics` |
| `finance_routes.py` | `/finance` | `/fees`, `/bursaries` |
| `governance_routes.py` | `/governance` | `/policies`, `/risks` |
| `onboarding_routes.py` | `/onboarding` | `/checklists`, `/items`, `/students`, `/reports`, `/sessions` |
| `pastoral_routes.py` | `/pastoral` | `/safeguarding`, `/behaviour` |
| `progression_routes.py` | `/progression` | `/ucas`, `/destinations`, `/fe-referrals`, `/linked-records`, `/incoming-fe-applications` |
| `reports_routes.py` | `/reports` | `/export`, `/kpi` |
| `staff_comms_routes.py` | `/staff-comms` | `/staff`, `/announcements` |
| `student_services_routes.py` | `/student-services` | `/admissions`, `/enrolments`, `/alumni` |
| `students_routes.py` | `/` | `/students`, `/identity` |

`applications_routes.py` and `applicant_portal_routes.py` are public-facing and are mounted by the unified server directly.

`routes/menu/` holds one module per main-menu category, each mounted at `/menu/<category>`, such as `/menu/student-management`. These are placeholders that report a pending feature. The other folders under `routes/` and the modules in `schemas/` are empty scaffolds.

Authentication routes are shared and live in `src/education_system/platform/delivery/api/routes/auth_routes.py`, including `POST /api/v1/auth/login`, `POST /api/v1/auth/mfa/verify`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/change-password`, `GET /api/v1/auth/me` and `POST /api/v1/auth/logout`.
