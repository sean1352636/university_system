"""Strawberry GraphQL schema: root Query + Mutation types, Flask view integration.

Mount points (registered in unified_server.py)
---------------------------------------------
- POST /api/v1/graphql      — GraphQL endpoint (production + development)
- GET  /api/v1/graphiql     — GraphiQL IDE (development only)
"""

from __future__ import annotations

from typing import List, Optional

import strawberry
from strawberry.flask.views import GraphQLView
from strawberry.types import Info

from .middleware import AuthMiddleware, DepthLimitMiddleware, RateLimitMiddleware
from .mutations import (
    AttendanceInput,
    GradeInput,
    StudentInput,
    resolve_create_enrollment,
    resolve_create_student,
    resolve_delete_student,
    resolve_record_attendance,
    resolve_record_grade,
    resolve_update_student,
)
from .resolvers import (
    resolve_attendance,
    resolve_course,
    resolve_courses,
    resolve_enrollments,
    resolve_grades,
    resolve_student,
    resolve_students,
    resolve_timetable,
)
from .types import (
    AttendanceType,
    CourseType,
    EnrollmentType,
    GradeType,
    StudentType,
    TimetableType,
)


# ---------------------------------------------------------------------------
# Root Query
# ---------------------------------------------------------------------------

def _user_info(info: Info) -> dict:
    context = info.context
    if isinstance(context, dict):
        user = context.get("user_info")
        if user:
            return dict(user)
    try:
        from flask import g
        return dict(getattr(g, "current_user", None) or {})
    except RuntimeError:
        return {}


def _require_authenticated(info: Info, *, roles: set[str] | None = None) -> dict:
    user = _user_info(info)
    if not user:
        raise PermissionError("Authentication is required")
    if roles and str(user.get("role", "")).lower() not in roles:
        raise PermissionError("Insufficient permissions")
    return user

@strawberry.type
class Query:
    @strawberry.field(description="List students/pupils for a given system.")
    def students(
        self,
        info: Info,
        system: str,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[StudentType]:
        _require_authenticated(info)
        return resolve_students(system, limit=limit, offset=offset, search=search)

    @strawberry.field(description="Fetch a single student by their student/pupil ID.")
    def student(
        self,
        info: Info,
        system: str,
        student_id: str,
    ) -> Optional[StudentType]:
        _require_authenticated(info)
        return resolve_student(system, student_id)

    @strawberry.field(description="List courses/subjects for a given system.")
    def courses(
        self,
        info: Info,
        system: str,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[CourseType]:
        _require_authenticated(info)
        return resolve_courses(system, limit=limit, offset=offset, search=search)

    @strawberry.field(description="Fetch a single course by its numeric ID.")
    def course(
        self,
        info: Info,
        system: str,
        course_id: str,
    ) -> Optional[CourseType]:
        _require_authenticated(info)
        return resolve_course(system, course_id)

    @strawberry.field(description="List grade records, optionally filtered by student.")
    def grades(
        self,
        info: Info,
        system: str,
        student_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GradeType]:
        _require_authenticated(info)
        return resolve_grades(system, student_id=student_id, limit=limit, offset=offset)

    @strawberry.field(description="List attendance records, optionally filtered.")
    def attendance(
        self,
        info: Info,
        system: str,
        student_id: Optional[str] = None,
        date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AttendanceType]:
        _require_authenticated(info)
        return resolve_attendance(
            system, student_id=student_id, date=date, limit=limit, offset=offset
        )

    @strawberry.field(description="List enrollment records, optionally filtered.")
    def enrollments(
        self,
        info: Info,
        system: str,
        student_id: Optional[str] = None,
        course_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EnrollmentType]:
        _require_authenticated(info)
        return resolve_enrollments(
            system, student_id=student_id, course_id=course_id,
            limit=limit, offset=offset,
        )

    @strawberry.field(description="List timetable slots, optionally filtered by course.")
    def timetable(
        self,
        info: Info,
        system: str,
        course_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TimetableType]:
        _require_authenticated(info)
        return resolve_timetable(system, course_id=course_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Root Mutation
# ---------------------------------------------------------------------------

@strawberry.type
class Mutation:
    @strawberry.mutation(description="Create a new student record.")
    def create_student(self, info: Info, system: str, input: StudentInput) -> StudentType:
        _require_authenticated(info, roles={"admin", "staff"})
        return resolve_create_student(system, input)

    @strawberry.mutation(description="Update an existing student record.")
    def update_student(
        self, info: Info, system: str, student_id: str, input: StudentInput
    ) -> StudentType:
        _require_authenticated(info, roles={"admin", "staff"})
        return resolve_update_student(system, student_id, input)

    @strawberry.mutation(description="Delete a student record. Returns True on success.")
    def delete_student(self, info: Info, system: str, student_id: str) -> bool:
        _require_authenticated(info, roles={"admin"})
        return resolve_delete_student(system, student_id)

    @strawberry.mutation(description="Enroll a student in a course/subject.")
    def create_enrollment(
        self, info: Info, system: str, student_id: str, course_id: str
    ) -> EnrollmentType:
        _require_authenticated(info, roles={"admin", "staff"})
        return resolve_create_enrollment(system, student_id, course_id)

    @strawberry.mutation(description="Record a grade for a student.")
    def record_grade(self, info: Info, system: str, input: GradeInput) -> GradeType:
        _require_authenticated(info, roles={"admin", "staff"})
        return resolve_record_grade(system, input)

    @strawberry.mutation(description="Record an attendance entry for a student.")
    def record_attendance(self, info: Info, system: str, input: AttendanceInput) -> AttendanceType:
        _require_authenticated(info, roles={"admin", "staff"})
        return resolve_record_attendance(system, input)


# ---------------------------------------------------------------------------
# Middleware stack
# ---------------------------------------------------------------------------

_extensions = [
    DepthLimitMiddleware(max_depth=10),
    AuthMiddleware,
    RateLimitMiddleware,
]

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=_extensions,
)


# ---------------------------------------------------------------------------
# Flask view factories
# ---------------------------------------------------------------------------

def make_graphql_view() -> GraphQLView:
    """Return a Flask view for the GraphQL POST endpoint."""
    return GraphQLView.as_view("graphql_view", schema=schema)


def make_graphiql_view() -> GraphQLView:
    """Return a Flask view for the GraphiQL IDE (development only)."""
    return GraphQLView.as_view(
        "graphiql_view",
        schema=schema,
        graphiql=True,
    )
