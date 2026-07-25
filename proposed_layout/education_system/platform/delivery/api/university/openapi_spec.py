"""OpenAPI 3.0.3 specification for the University Management System API.

The spec is built once as a Python dict and cached for the lifetime of the
process.  Helper functions keep the ~60-endpoint definition DRY.
"""

from __future__ import annotations

import functools
from typing import Any

_SPEC_VERSION = "5.46.3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pagination_params() -> list[dict]:
    """Common query parameters for paginated list endpoints."""
    return [
        {
            "name": "page",
            "in": "query",
            "schema": {"type": "integer", "default": 1, "minimum": 1},
            "description": "Page number",
        },
        {
            "name": "per_page",
            "in": "query",
            "schema": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
            "description": "Items per page",
        },
    ]


def _error_responses() -> dict:
    """Standard error responses shared by most endpoints."""
    return {
        "400": {
            "description": "Validation error",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        },
        "401": {
            "description": "Missing or invalid JWT token",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        },
        "404": {
            "description": "Resource not found",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        },
    }


def _crud_paths(
    prefix: str,
    tag: str,
    resource: str,
    *,
    plural: str | None = None,
    id_param: str = "id",
    id_type: str = "integer",
    extra_list_params: list[dict] | None = None,
    has_create: bool = True,
    has_update: bool = True,
    has_delete: bool = True,
    extra_paths: dict | None = None,
) -> dict:
    """Generate standard CRUD paths for a resource group.

    Returns a dict of ``{path: {method: operation}}`` suitable for merging
    into the top-level ``paths`` object.
    """
    plural = plural or (resource + "s")
    paths: dict[str, Any] = {}

    # -- LIST --
    list_params: list[dict] = list(_pagination_params())
    list_params.append({
        "name": "search",
        "in": "query",
        "schema": {"type": "string"},
        "description": f"Search {plural}",
    })
    if extra_list_params:
        list_params.extend(extra_list_params)

    list_path = paths.setdefault(prefix, {})
    list_path["get"] = {
        "tags": [tag],
        "summary": f"List {plural}",
        "security": [{"BearerAuth": []}],
        "parameters": list_params,
        "responses": {
            "200": {"description": f"List of {plural}"},
            **_error_responses(),
        },
    }

    # -- CREATE --
    if has_create:
        list_path["post"] = {
            "tags": [tag],
            "summary": f"Create {resource}",
            "security": [{"BearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "responses": {
                "201": {"description": f"{resource.title()} created"},
                **_error_responses(),
            },
        }

    # -- GET by ID --
    detail_path_str = f"{prefix}/{{{id_param}}}"
    detail_path = paths.setdefault(detail_path_str, {})
    id_schema: dict[str, Any] = {"type": id_type}
    detail_path["get"] = {
        "tags": [tag],
        "summary": f"Get {resource} by ID",
        "security": [{"BearerAuth": []}],
        "parameters": [
            {"name": id_param, "in": "path", "required": True, "schema": id_schema},
        ],
        "responses": {
            "200": {"description": f"{resource.title()} details"},
            **_error_responses(),
        },
    }

    # -- UPDATE --
    if has_update:
        detail_path["put"] = {
            "tags": [tag],
            "summary": f"Update {resource}",
            "security": [{"BearerAuth": []}],
            "parameters": [
                {"name": id_param, "in": "path", "required": True, "schema": id_schema},
            ],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "responses": {
                "200": {"description": f"{resource.title()} updated"},
                **_error_responses(),
            },
        }

    # -- DELETE --
    if has_delete:
        detail_path["delete"] = {
            "tags": [tag],
            "summary": f"Delete {resource}",
            "security": [{"BearerAuth": []}],
            "parameters": [
                {"name": id_param, "in": "path", "required": True, "schema": id_schema},
            ],
            "responses": {
                "200": {"description": f"{resource.title()} deleted"},
                **_error_responses(),
            },
        }

    # -- Extra paths --
    if extra_paths:
        paths.update(extra_paths)

    return paths


# ---------------------------------------------------------------------------
# Tier 1 – fully documented paths
# ---------------------------------------------------------------------------

def _auth_paths() -> dict:
    return {
        "/api/auth/login": {
            "post": {
                "tags": ["Authentication"],
                "summary": "Login and obtain JWT tokens",
                "description": (
                    "Authenticate with username and password to receive an "
                    "access token and a refresh token.  Use the access token "
                    "in the `Authorization: Bearer <token>` header for all "
                    "subsequent requests."
                ),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LoginRequest"},
                            "example": {"username": "admin", "password": "Admin123"},
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Successful login",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/LoginResponse"},
                            }
                        },
                    },
                    "400": {"description": "Missing credentials"},
                    "401": {"description": "Invalid credentials"},
                },
            },
        },
        "/api/auth/logout": {
            "post": {
                "tags": ["Authentication"],
                "summary": "Logout (blacklist current token)",
                "security": [{"BearerAuth": []}],
                "responses": {
                    "200": {"description": "Successfully logged out"},
                    "401": {"description": "Missing or invalid token"},
                },
            },
        },
        "/api/auth/refresh": {
            "post": {
                "tags": ["Authentication"],
                "summary": "Refresh access token",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["refresh_token"],
                                "properties": {
                                    "refresh_token": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "New access token",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "access_token": {"type": "string"},
                                    },
                                },
                            }
                        },
                    },
                    "401": {"description": "Invalid or expired refresh token"},
                },
            },
        },
        "/api/auth/me": {
            "get": {
                "tags": ["Authentication"],
                "summary": "Get current user info",
                "security": [{"BearerAuth": []}],
                "responses": {
                    "200": {
                        "description": "Current user details",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string"},
                                        "user_id": {"type": "integer"},
                                        "role": {"type": "string"},
                                    },
                                },
                            }
                        },
                    },
                    "401": {"description": "Not authenticated"},
                },
            },
        },
    }


def _student_paths() -> dict:
    return {
        "/api/students": {
            "get": {
                "tags": ["Students"],
                "summary": "List students",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    *_pagination_params(),
                    {"name": "search", "in": "query", "schema": {"type": "string"}, "description": "Search by name or ID"},
                    {"name": "status", "in": "query", "schema": {"type": "string"}, "description": "Filter by status (e.g. Active)"},
                    {"name": "course", "in": "query", "schema": {"type": "string"}, "description": "Filter by course"},
                ],
                "responses": {
                    "200": {
                        "description": "Paginated student list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "items": {"type": "array", "items": {"$ref": "#/components/schemas/Student"}},
                                        "total": {"type": "integer"},
                                        "page": {"type": "integer"},
                                        "per_page": {"type": "integer"},
                                        "pages": {"type": "integer"},
                                    },
                                },
                            }
                        },
                    },
                    **_error_responses(),
                },
            },
            "post": {
                "tags": ["Students"],
                "summary": "Create a new student",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/StudentCreate"},
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Student created",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Student"}}},
                    },
                    **_error_responses(),
                },
            },
        },
        "/api/students/{student_id}": {
            "get": {
                "tags": ["Students"],
                "summary": "Get student by ID",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    {"name": "student_id", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {
                        "description": "Student details",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Student"}}},
                    },
                    **_error_responses(),
                },
            },
            "put": {
                "tags": ["Students"],
                "summary": "Update student",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    {"name": "student_id", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/StudentCreate"}}},
                },
                "responses": {
                    "200": {"description": "Student updated", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Student"}}}},
                    **_error_responses(),
                },
            },
            "delete": {
                "tags": ["Students"],
                "summary": "Delete student",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    {"name": "student_id", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {"description": "Student deleted"},
                    **_error_responses(),
                },
            },
        },
    }


def _course_paths() -> dict:
    return {
        "/api/courses": {
            "get": {
                "tags": ["Academics"],
                "summary": "List courses",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    *_pagination_params(),
                    {"name": "search", "in": "query", "schema": {"type": "string"}, "description": "Search by code or name"},
                    {"name": "department", "in": "query", "schema": {"type": "string"}, "description": "Filter by department"},
                ],
                "responses": {
                    "200": {
                        "description": "Paginated course list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "items": {"type": "array", "items": {"$ref": "#/components/schemas/Course"}},
                                        "total": {"type": "integer"},
                                        "page": {"type": "integer"},
                                        "per_page": {"type": "integer"},
                                        "pages": {"type": "integer"},
                                    },
                                },
                            }
                        },
                    },
                    **_error_responses(),
                },
            },
            "post": {
                "tags": ["Academics"],
                "summary": "Create a new course",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CourseCreate"}}},
                },
                "responses": {
                    "201": {"description": "Course created", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Course"}}}},
                    **_error_responses(),
                },
            },
        },
        "/api/courses/{course_id}": {
            "get": {
                "tags": ["Academics"],
                "summary": "Get course by ID",
                "security": [{"BearerAuth": []}],
                "parameters": [{"name": "course_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {
                    "200": {"description": "Course details", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Course"}}}},
                    **_error_responses(),
                },
            },
            "put": {
                "tags": ["Academics"],
                "summary": "Update course",
                "security": [{"BearerAuth": []}],
                "parameters": [{"name": "course_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CourseCreate"}}},
                },
                "responses": {"200": {"description": "Course updated"}, **_error_responses()},
            },
        },
        "/api/courses/{course_id}/waitlist": {
            "get": {
                "tags": ["Academics"],
                "summary": "Get course waitlist",
                "security": [{"BearerAuth": []}],
                "parameters": [{"name": "course_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Course waitlist entries"}, **_error_responses()},
            },
        },
    }


def _grade_paths() -> dict:
    return {
        "/api/grades": {
            "get": {
                "tags": ["Grades & Assessments"],
                "summary": "List grades",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    {"name": "student_id", "in": "query", "schema": {"type": "string"}, "description": "Filter by student ID"},
                    {"name": "assessment_id", "in": "query", "schema": {"type": "integer"}, "description": "Filter by assessment ID"},
                ],
                "responses": {
                    "200": {
                        "description": "List of grades",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "items": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "grade_id": {"type": "integer"},
                                                    "student_id": {"type": "string"},
                                                    "assessment_id": {"type": "integer"},
                                                    "score": {"type": "number"},
                                                    "letter_grade": {"type": "string"},
                                                    "submission_date": {"type": "string"},
                                                    "comments": {"type": "string"},
                                                },
                                            },
                                        },
                                        "total": {"type": "integer"},
                                    },
                                },
                            }
                        },
                    },
                    **_error_responses(),
                },
            },
            "post": {
                "tags": ["Grades & Assessments"],
                "summary": "Record a grade",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["student_id"],
                                "properties": {
                                    "student_id": {"type": "string"},
                                    "assessment_id": {"type": "integer"},
                                    "score": {"type": "number"},
                                    "letter_grade": {"type": "string"},
                                    "comments": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                "responses": {"201": {"description": "Grade recorded"}, **_error_responses()},
            },
        },
        "/api/grades/{grade_id}": {
            "put": {
                "tags": ["Grades & Assessments"],
                "summary": "Update a grade",
                "security": [{"BearerAuth": []}],
                "parameters": [{"name": "grade_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "score": {"type": "number"},
                                    "letter_grade": {"type": "string"},
                                    "comments": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                "responses": {"200": {"description": "Grade updated"}, **_error_responses()},
            },
        },
    }


def _finance_paths() -> dict:
    return {
        "/api/finance/fees": {
            "get": {
                "tags": ["Finance"],
                "summary": "List fees for a student",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    {"name": "student_id", "in": "query", "required": True, "schema": {"type": "string"}, "description": "Student ID"},
                ],
                "responses": {"200": {"description": "Student fee records"}, **_error_responses()},
            },
        },
        "/api/finance/payments": {
            "get": {
                "tags": ["Finance"],
                "summary": "List payments",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    *_pagination_params(),
                    {"name": "student_id", "in": "query", "schema": {"type": "string"}, "description": "Filter by student ID"},
                ],
                "responses": {"200": {"description": "Paginated payment list"}, **_error_responses()},
            },
            "post": {
                "tags": ["Finance"],
                "summary": "Record a payment",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["student_id", "amount", "payment_type"],
                                "properties": {
                                    "student_id": {"type": "string"},
                                    "amount": {"type": "number"},
                                    "payment_type": {"type": "string"},
                                    "description": {"type": "string"},
                                    "status": {"type": "string", "default": "completed"},
                                },
                            },
                        }
                    },
                },
                "responses": {"201": {"description": "Payment recorded"}, **_error_responses()},
            },
        },
        "/api/finance/scholarships": {
            "get": {
                "tags": ["Finance"],
                "summary": "List active scholarships",
                "security": [{"BearerAuth": []}],
                "parameters": _pagination_params(),
                "responses": {"200": {"description": "Paginated scholarship list"}, **_error_responses()},
            },
        },
        "/api/finance/account/{student_id}": {
            "get": {
                "tags": ["Finance"],
                "summary": "Get student account balance",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    {"name": "student_id", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {
                        "description": "Account balance summary",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "student_id": {"type": "string"},
                                        "total_fees": {"type": "number"},
                                        "total_payments": {"type": "number"},
                                        "balance": {"type": "number"},
                                    },
                                },
                            }
                        },
                    },
                    **_error_responses(),
                },
            },
        },
    }


def _user_paths() -> dict:
    return {
        "/api/users": {
            "get": {
                "tags": ["Users & Dashboard"],
                "summary": "List users (admin only)",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    *_pagination_params(),
                    {"name": "role", "in": "query", "schema": {"type": "string", "enum": ["admin", "instructor", "student", "staff"]}, "description": "Filter by role"},
                    {"name": "search", "in": "query", "schema": {"type": "string"}, "description": "Search by username or email"},
                ],
                "responses": {"200": {"description": "Paginated user list"}, **_error_responses()},
            },
            "post": {
                "tags": ["Users & Dashboard"],
                "summary": "Create user (admin only)",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["username", "password", "role"],
                                "properties": {
                                    "username": {"type": "string"},
                                    "password": {"type": "string", "format": "password"},
                                    "role": {"type": "string", "enum": ["admin", "instructor", "student", "staff"]},
                                    "email": {"type": "string", "format": "email"},
                                },
                            },
                        }
                    },
                },
                "responses": {"201": {"description": "User created"}, **_error_responses()},
            },
        },
        "/api/users/{user_id}": {
            "get": {
                "tags": ["Users & Dashboard"],
                "summary": "Get user by ID",
                "security": [{"BearerAuth": []}],
                "parameters": [{"name": "user_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "User details"}, **_error_responses()},
            },
            "put": {
                "tags": ["Users & Dashboard"],
                "summary": "Update user (admin only)",
                "security": [{"BearerAuth": []}],
                "parameters": [{"name": "user_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "responses": {"200": {"description": "User updated"}, **_error_responses()},
            },
            "delete": {
                "tags": ["Users & Dashboard"],
                "summary": "Deactivate user (admin only)",
                "security": [{"BearerAuth": []}],
                "parameters": [{"name": "user_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "User deactivated"}, **_error_responses()},
            },
        },
    }


def _mfa_paths() -> dict:
    """MFA management and login verification endpoints."""
    mfa_tag = "MFA Management"
    auth_tag = "Authentication"
    return {
        "/api/auth/mfa/verify": {
            "post": {
                "tags": [auth_tag],
                "summary": "Verify MFA code during login",
                "description": "Submit an MFA code to complete login. Requires an mfa_token from the login response.",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["code"],
                                "properties": {
                                    "code": {"type": "string", "description": "MFA verification code"},
                                    "method": {"type": "string", "enum": ["totp", "sms", "email", "recovery"], "default": "totp"},
                                    "device_id": {"type": "string", "description": "Optional device ID for trust"},
                                },
                            },
                        }
                    },
                },
                "responses": {
                    "200": {"description": "MFA verified, tokens returned"},
                    "401": {"description": "Invalid MFA code or token"},
                },
            },
        },
        "/api/auth/mfa/send-code": {
            "post": {
                "tags": [auth_tag],
                "summary": "Send MFA code via SMS or email",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "method": {"type": "string", "enum": ["sms", "email"]},
                                    "phone": {"type": "string"},
                                    "email": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                "responses": {
                    "200": {"description": "Code sent successfully"},
                    **_error_responses(),
                },
            },
        },
        "/api/mfa/status": {
            "get": {
                "tags": [mfa_tag],
                "summary": "Get MFA status and configured methods",
                "security": [{"BearerAuth": []}],
                "responses": {
                    "200": {"description": "MFA status"},
                    **_error_responses(),
                },
            },
        },
        "/api/mfa/setup/totp": {
            "post": {
                "tags": [mfa_tag],
                "summary": "Begin TOTP authenticator setup",
                "security": [{"BearerAuth": []}],
                "responses": {
                    "200": {"description": "TOTP secret and provisioning URI"},
                    **_error_responses(),
                },
            },
        },
        "/api/mfa/setup/totp/verify": {
            "post": {
                "tags": [mfa_tag],
                "summary": "Verify TOTP code to confirm setup",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object", "required": ["code"], "properties": {"code": {"type": "string"}}}}},
                },
                "responses": {"200": {"description": "TOTP setup confirmed"}, **_error_responses()},
            },
        },
        "/api/mfa/setup/sms": {
            "post": {
                "tags": [mfa_tag],
                "summary": "Send OTP for SMS MFA setup",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object", "required": ["phone"], "properties": {"phone": {"type": "string"}}}}},
                },
                "responses": {"200": {"description": "SMS code sent"}, **_error_responses()},
            },
        },
        "/api/mfa/setup/sms/verify": {
            "post": {
                "tags": [mfa_tag],
                "summary": "Verify SMS code to confirm setup",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object", "required": ["code"], "properties": {"code": {"type": "string"}}}}},
                },
                "responses": {"200": {"description": "SMS MFA setup confirmed"}, **_error_responses()},
            },
        },
        "/api/mfa/setup/email": {
            "post": {
                "tags": [mfa_tag],
                "summary": "Send OTP for email MFA setup",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object", "required": ["email"], "properties": {"email": {"type": "string"}}}}},
                },
                "responses": {"200": {"description": "Email code sent"}, **_error_responses()},
            },
        },
        "/api/mfa/setup/email/verify": {
            "post": {
                "tags": [mfa_tag],
                "summary": "Verify email code to confirm setup",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object", "required": ["code"], "properties": {"code": {"type": "string"}}}}},
                },
                "responses": {"200": {"description": "Email MFA setup confirmed"}, **_error_responses()},
            },
        },
        "/api/mfa/recovery-codes": {
            "post": {
                "tags": [mfa_tag],
                "summary": "Generate new recovery codes",
                "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "Recovery codes generated"}, **_error_responses()},
            },
        },
        "/api/mfa/enable": {
            "post": {
                "tags": [mfa_tag],
                "summary": "Enable MFA for current user",
                "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "MFA enabled"}, **_error_responses()},
            },
        },
        "/api/mfa/disable": {
            "post": {
                "tags": [mfa_tag],
                "summary": "Disable MFA for current user",
                "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "MFA disabled"}, **_error_responses()},
            },
        },
        "/api/mfa/trusted-devices": {
            "get": {
                "tags": [mfa_tag],
                "summary": "List trusted devices",
                "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "List of trusted devices"}, **_error_responses()},
            },
        },
        "/api/mfa/trusted-devices/{device_id}": {
            "delete": {
                "tags": [mfa_tag],
                "summary": "Revoke trusted device",
                "security": [{"BearerAuth": []}],
                "parameters": [{"name": "device_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "Device trust revoked"}, **_error_responses()},
            },
        },
    }


def _account_paths() -> dict:
    """Account settings endpoints."""
    tag = "Account Settings"
    return {
        "/api/account/profile": {
            "get": {
                "tags": [tag],
                "summary": "Get current user profile",
                "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "User profile"}, **_error_responses()},
            },
            "put": {
                "tags": [tag],
                "summary": "Update own profile",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "first_name": {"type": "string"},
                                    "last_name": {"type": "string"},
                                    "email": {"type": "string", "format": "email"},
                                    "phone": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                "responses": {"200": {"description": "Profile updated"}, **_error_responses()},
            },
        },
        "/api/account/password": {
            "put": {
                "tags": [tag],
                "summary": "Change own password",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["current_password", "new_password"],
                                "properties": {
                                    "current_password": {"type": "string"},
                                    "new_password": {"type": "string", "minLength": 8},
                                },
                            },
                        }
                    },
                },
                "responses": {"200": {"description": "Password changed"}, **_error_responses()},
            },
        },
        "/api/account/preferences": {
            "get": {
                "tags": [tag],
                "summary": "Get user preferences",
                "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "User preferences"}, **_error_responses()},
            },
            "put": {
                "tags": [tag],
                "summary": "Update user preferences",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "theme": {"type": "string", "enum": ["light", "dark"]},
                                    "language": {"type": "string"},
                                    "timezone": {"type": "string"},
                                    "email_notifications": {"type": "boolean"},
                                    "sms_notifications": {"type": "boolean"},
                                },
                            },
                        }
                    },
                },
                "responses": {"200": {"description": "Preferences updated"}, **_error_responses()},
            },
        },
        "/api/account/sessions": {
            "get": {
                "tags": [tag],
                "summary": "Get recent login sessions",
                "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "Login history"}, **_error_responses()},
            },
        },
    }


def _dashboard_paths() -> dict:
    return {
        "/api/dashboard/stats": {
            "get": {
                "tags": ["Users & Dashboard"],
                "summary": "Get aggregate dashboard statistics",
                "description": "Returns record counts for all major tables (students, courses, payments, etc.).",
                "security": [{"BearerAuth": []}],
                "responses": {
                    "200": {
                        "description": "Dashboard statistics",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "stats": {
                                            "type": "object",
                                            "additionalProperties": {"type": "integer"},
                                        },
                                    },
                                },
                            }
                        },
                    },
                    **_error_responses(),
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Tier 2 – generated via _crud_paths helper
# ---------------------------------------------------------------------------

def _tier2_paths() -> dict:
    """Build paths for the remaining endpoint groups."""
    paths: dict[str, Any] = {}

    groups = [
        # (prefix, tag, resource_singular, overrides)
        ("/api/modules", "Academics", "module", {}),
        ("/api/enrollments", "Students", "enrollment", {"id_param": "enrollment_id"}),
        ("/api/degrees", "Academics", "degree program", {"plural": "degree programs", "id_param": "program_id"}),
        ("/api/timetable", "Academics", "timetable entry", {"plural": "timetable entries", "id_param": "entry_id", "has_delete": False}),
        ("/api/assessments", "Grades & Assessments", "assessment", {"id_param": "assessment_id"}),
        ("/api/assignments", "Grades & Assessments", "assignment", {"id_param": "assignment_id"}),
        ("/api/exams", "Grades & Assessments", "exam", {"id_param": "exam_id"}),
        ("/api/attendance", "Attendance", "attendance session", {"plural": "attendance sessions", "id_param": "session_id"}),
        ("/api/financial-aid", "Finance", "financial aid application", {"plural": "financial aid applications", "id_param": "application_id"}),
        ("/api/scholarships", "Finance", "scholarship", {"id_param": "scholarship_id"}),
        ("/api/hr", "Human Resources", "staff member", {"plural": "staff members", "id_param": "staff_id"}),
        ("/api/health-services", "Health & Wellness", "health appointment", {"plural": "health appointments", "id_param": "appointment_id"}),
        ("/api/counseling", "Health & Wellness", "counseling appointment", {"plural": "counseling appointments", "id_param": "appointment_id"}),
        ("/api/housing", "Housing", "housing application", {"plural": "housing applications", "id_param": "application_id"}),
        ("/api/accommodations", "Housing", "accommodation request", {"plural": "accommodation requests", "id_param": "request_id"}),
        ("/api/campus", "Campus & Facilities", "campus resource", {"plural": "campus resources", "id_param": "resource_id"}),
        ("/api/facilities", "Campus & Facilities", "facility booking", {"plural": "facility bookings", "id_param": "booking_id"}),
        ("/api/parking", "Campus & Facilities", "parking permit", {"plural": "parking permits", "id_param": "permit_id"}),
        ("/api/security", "Campus & Facilities", "security ticket", {"plural": "security tickets", "id_param": "ticket_id"}),
        ("/api/equipment", "Campus & Facilities", "equipment item", {"plural": "equipment items", "id_param": "item_id"}),
        ("/api/lost-found", "Campus & Facilities", "lost & found item", {"plural": "lost & found items", "id_param": "item_id"}),
        ("/api/clubs", "Student Life", "club", {"id_param": "club_id"}),
        ("/api/events", "Student Life", "event", {"id_param": "event_id"}),
        ("/api/study-groups", "Student Life", "study group", {"plural": "study groups", "id_param": "group_id"}),
        ("/api/mentorship", "Student Life", "mentorship", {"plural": "mentorships", "id_param": "relationship_id"}),
        ("/api/tutoring", "Student Life", "tutoring offer", {"plural": "tutoring offers", "id_param": "offer_id"}),
        ("/api/dining", "Student Life", "dining resource", {"plural": "dining resources", "id_param": "resource_id", "has_delete": False}),
        ("/api/notifications", "Communication", "notification", {"id_param": "notification_id"}),
        ("/api/announcements", "Communication", "announcement", {"id_param": "announcement_id"}),
        ("/api/communication", "Communication", "message", {"id_param": "message_id"}),
        ("/api/chat", "Communication", "chat room", {"plural": "chat rooms", "id_param": "room_id"}),
        ("/api/lms", "Learning Management", "LMS course", {"plural": "LMS courses", "id_param": "course_id"}),
        ("/api/virtual-classrooms", "Learning Management", "virtual classroom", {"plural": "virtual classrooms", "id_param": "classroom_id"}),
        ("/api/integrity", "Learning Management", "misconduct case", {"plural": "misconduct cases", "id_param": "case_id"}),
        ("/api/office-hours", "Learning Management", "office hours slot", {"plural": "office hours slots", "id_param": "slot_id"}),
        ("/api/ta", "Learning Management", "TA assignment", {"plural": "TA assignments", "id_param": "assignment_id"}),
        ("/api/evaluations", "Learning Management", "course evaluation", {"plural": "course evaluations", "id_param": "evaluation_id"}),
        ("/api/career", "Career & Research", "career posting", {"plural": "career postings", "id_param": "posting_id"}),
        ("/api/research", "Career & Research", "research project", {"plural": "research projects", "id_param": "project_id"}),
        ("/api/admissions", "Career & Research", "admission application", {"plural": "admission applications", "id_param": "application_id"}),
        ("/api/alumni", "Career & Research", "alumnus", {"plural": "alumni", "id_param": "alumni_id"}),
        ("/api/calendar", "Administration", "calendar event", {"plural": "calendar events", "id_param": "event_id"}),
        ("/api/advising", "Administration", "advising appointment", {"plural": "advising appointments", "id_param": "appointment_id"}),
        ("/api/early-warning", "Administration", "early warning profile", {"plural": "early warning profiles", "id_param": "profile_id"}),
        ("/api/documents", "Administration", "document", {"id_param": "document_id"}),
        ("/api/credentials", "Administration", "credential", {"id_param": "credential_id"}),
        ("/api/elections", "Administration", "election", {"id_param": "election_id"}),
        ("/api/parents", "Administration", "parent account", {"plural": "parent accounts", "id_param": "parent_id"}),
        ("/api/helpdesk", "Administration", "support ticket", {"plural": "support tickets", "id_param": "ticket_id"}),
    ]

    for prefix, tag, resource, overrides in groups:
        crud = _crud_paths(prefix, tag, resource, **overrides)
        for path, methods in crud.items():
            paths.setdefault(path, {}).update(methods)

    return paths


# ---------------------------------------------------------------------------
# System / health paths
# ---------------------------------------------------------------------------

def _system_paths() -> dict:
    return {
        "/api": {
            "get": {
                "tags": ["System"],
                "summary": "API index — list all endpoints",
                "responses": {"200": {"description": "Endpoint listing with version info"}},
            },
        },
        "/api/health": {
            "get": {
                "tags": ["System"],
                "summary": "Health check",
                "responses": {
                    "200": {
                        "description": "Service is healthy",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "healthy"},
                                        "timestamp": {"type": "string", "format": "date-time"},
                                    },
                                },
                            }
                        },
                    },
                },
            },
        },
        "/api/version": {
            "get": {
                "tags": ["System"],
                "summary": "API version info",
                "responses": {"200": {"description": "Version details"}},
            },
        },
    }


# ---------------------------------------------------------------------------
# Component schemas
# ---------------------------------------------------------------------------

def _component_schemas() -> dict:
    return {
        "LoginRequest": {
            "type": "object",
            "required": ["username", "password"],
            "properties": {
                "username": {"type": "string", "example": "admin"},
                "password": {"type": "string", "format": "password", "example": "Admin123"},
            },
        },
        "LoginResponse": {
            "type": "object",
            "properties": {
                "access_token": {"type": "string"},
                "refresh_token": {"type": "string"},
                "user": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "role": {"type": "string"},
                        "user_id": {"type": "integer"},
                    },
                },
            },
        },
        "Student": {
            "type": "object",
            "properties": {
                "student_id": {"type": "string", "example": "STU2023001"},
                "first_name": {"type": "string"},
                "middle_name": {"type": "string", "nullable": True},
                "last_name": {"type": "string"},
                "full_name": {"type": "string"},
                "email_address": {"type": "string", "format": "email"},
                "title": {"type": "string", "nullable": True},
                "gender": {"type": "string", "nullable": True},
                "dob": {"type": "string", "format": "date", "nullable": True},
                "age": {"type": "integer", "nullable": True},
                "course": {"type": "string", "nullable": True},
                "status": {"type": "string", "example": "Active"},
                "enrollment_date": {"type": "string", "format": "date", "nullable": True},
                "registration_datetime": {"type": "string", "format": "date-time", "nullable": True},
            },
        },
        "StudentCreate": {
            "type": "object",
            "required": ["student_id", "first_name", "last_name"],
            "properties": {
                "student_id": {"type": "string", "example": "STU2023001"},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "middle_name": {"type": "string"},
                "email_address": {"type": "string", "format": "email"},
                "title": {"type": "string"},
                "gender": {"type": "string"},
                "dob": {"type": "string", "format": "date"},
                "age": {"type": "integer"},
                "course": {"type": "string"},
                "status": {"type": "string", "default": "Active"},
                "enrollment_date": {"type": "string", "format": "date"},
            },
        },
        "Course": {
            "type": "object",
            "properties": {
                "course_id": {"type": "integer"},
                "course_code": {"type": "string", "example": "CS101"},
                "course_name": {"type": "string"},
                "description": {"type": "string"},
                "department": {"type": "string"},
                "credits": {"type": "integer"},
                "max_capacity": {"type": "integer"},
                "status": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
            },
        },
        "CourseCreate": {
            "type": "object",
            "required": ["course_code", "course_name"],
            "properties": {
                "course_code": {"type": "string", "example": "CS101"},
                "course_name": {"type": "string", "example": "Introduction to Computer Science"},
                "description": {"type": "string"},
                "department": {"type": "string"},
                "credits": {"type": "integer", "default": 0},
                "max_capacity": {"type": "integer", "default": 30},
                "status": {"type": "string", "default": "active"},
            },
        },
        "Error": {
            "type": "object",
            "properties": {
                "error": {"type": "string"},
                "status": {"type": "integer"},
            },
        },
        "PaginationMeta": {
            "type": "object",
            "properties": {
                "total": {"type": "integer"},
                "page": {"type": "integer"},
                "per_page": {"type": "integer"},
                "pages": {"type": "integer"},
            },
        },
    }


def _analytics_paths() -> dict:
    """Institutional analytics: computed cross-module aggregate metrics.

    All endpoints are GET-only, require a JWT, and are restricted to
    non-student roles (a ``student`` role receives 403).
    """
    tag = "Institutional Analytics"

    def _get(summary: str, description: str, parameters: list | None = None) -> dict:
        op: dict[str, Any] = {
            "tags": [tag],
            "summary": summary,
            "description": description,
            "security": [{"BearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Analytics payload",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"data": {"type": "object"}},
                            }
                        }
                    },
                },
                "403": {
                    "description": "Staff access required (student role denied)",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    },
                },
                **_error_responses(),
            },
        }
        if parameters:
            op["parameters"] = parameters
        return {"get": op}

    return {
        "/api/analytics/overview": _get(
            "Institutional overview",
            "Headline figures plus every analytics section in one payload. "
            "Sections whose source data is unavailable are reported under "
            "`data.errors` rather than failing the request.",
        ),
        "/api/analytics/enrollment": _get(
            "Enrolment summary",
            "Head-count with current/completed/attrition split and a breakdown "
            "by course.",
        ),
        "/api/analytics/retention": _get(
            "Retention & attrition",
            "Retention, attrition and completion rates, overall and per course.",
        ),
        "/api/analytics/modules": _get(
            "Module performance",
            "Per-module enrolment volume, pass rate and in-progress counts.",
            parameters=[
                {
                    "name": "limit",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "minimum": 1},
                    "description": "Return only the top N modules by enrolment.",
                }
            ],
        ),
        "/api/analytics/capacity": _get(
            "Course capacity",
            "Fill rate (enrolment vs capacity) per course and institution-wide.",
        ),
        "/api/analytics/finance": _get(
            "Financial summary",
            "Collected revenue (by method and month), outstanding vs waived "
            "fees, and finance account balances.",
        ),
        "/api/analytics/demographics": _get(
            "Demographics",
            "Gender split plus age, UCAS-tariff and GPA summaries where "
            "available.",
        ),
    }


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

_TAGS = [
    {"name": "System", "description": "Health checks, version info, and API index"},
    {"name": "Authentication", "description": "Login, logout, token refresh, MFA verification, and current user"},
    {"name": "MFA Management", "description": "Multi-factor authentication setup and management"},
    {"name": "Account Settings", "description": "User profile, password, preferences, and sessions"},
    {"name": "Students", "description": "Student records and enrollment management"},
    {"name": "Academics", "description": "Courses, modules, degrees, and timetables"},
    {"name": "Grades & Assessments", "description": "Grades, assessments, assignments, and exams"},
    {"name": "Attendance", "description": "Attendance sessions and records"},
    {"name": "Finance", "description": "Fees, payments, scholarships, and financial aid"},
    {"name": "Users & Dashboard", "description": "User administration and system dashboard"},
    {"name": "Human Resources", "description": "Staff management, leave, shifts, and timesheets"},
    {"name": "Health & Wellness", "description": "Health services and counseling appointments"},
    {"name": "Housing", "description": "Housing applications and accommodation requests"},
    {"name": "Campus & Facilities", "description": "Campus resources, facilities, parking, security, equipment, and lost & found"},
    {"name": "Student Life", "description": "Clubs, events, study groups, mentorship, tutoring, and dining"},
    {"name": "Communication", "description": "Notifications, announcements, messaging, and chat"},
    {"name": "Learning Management", "description": "LMS, virtual classrooms, academic integrity, office hours, TAs, and evaluations"},
    {"name": "Career & Research", "description": "Career services, research projects, admissions, and alumni"},
    {"name": "Administration", "description": "Calendar, advising, early warning, documents, credentials, elections, parents, and helpdesk"},
    {"name": "Institutional Analytics", "description": "Computed cross-module aggregate metrics: enrolment, retention, module performance, capacity, finance, and demographics"},
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def get_openapi_spec() -> dict:
    """Return the complete OpenAPI 3.0.3 specification as a dict."""
    paths: dict[str, Any] = {}

    for source in (
        _system_paths,
        _auth_paths,
        _mfa_paths,
        _account_paths,
        _student_paths,
        _course_paths,
        _grade_paths,
        _finance_paths,
        _user_paths,
        _dashboard_paths,
        _analytics_paths,
        _tier2_paths,
    ):
        for path, methods in source().items():
            paths.setdefault(path, {}).update(methods)

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "University Management System API",
            "version": _SPEC_VERSION,
            "description": (
                "REST API for the University Management System.\n\n"
                "## Quick Start\n"
                "1. **Login** — `POST /api/auth/login` with "
                '`{"username": "admin", "password": "Admin123"}`\n'
                "2. **Copy** the `access_token` from the response\n"
                "3. **Authorize** — Click the **Authorize** button above and "
                "enter `Bearer <your-token>`\n"
                "4. **Explore** — Try any endpoint (e.g. `GET /api/students`)\n"
            ),
        },
        "servers": [
            {"url": "/", "description": "Current server"},
        ],
        "tags": _TAGS,
        "paths": paths,
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT access token obtained from POST /api/auth/login",
                },
            },
            "schemas": _component_schemas(),
        },
    }
