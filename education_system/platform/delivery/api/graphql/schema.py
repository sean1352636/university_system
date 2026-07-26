"""Strawberry GraphQL schema: root Query + Mutation types, Flask view integration.

Mount points (registered in unified_server.py)
---------------------------------------------
- POST /api/v1/graphql      — GraphQL endpoint (production + development)
- GET  /api/v1/graphiql     — GraphiQL IDE (development only)
"""

from __future__ import annotations

import os
from typing import List, Optional

import strawberry
from strawberry.flask.views import GraphQLView

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

@strawberry.type
class Query:
    @strawberry.field(description="List students/pupils for a given system.")
    def students(
        self,
        system: str,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[StudentType]:
        return resolve_students(system, limit=limit, offset=offset, search=search)

    @strawberry.field(description="Fetch a single student by their student/pupil ID.")
    def student(
        self,
        system: str,
        student_id: str,
    ) -> Optional[StudentType]:
        return resolve_student(system, student_id)

    @strawberry.field(description="List courses/subjects for a given system.")
    def courses(
        self,
        system: str,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[CourseType]:
        return resolve_courses(system, limit=limit, offset=offset, search=search)

    @strawberry.field(description="Fetch a single course by its numeric ID.")
    def course(
        self,
        system: str,
        course_id: str,
    ) -> Optional[CourseType]:
        return resolve_course(system, course_id)

    @strawberry.field(description="List grade records, optionally filtered by student.")
    def grades(
        self,
        system: str,
        student_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GradeType]:
        return resolve_grades(system, student_id=student_id, limit=limit, offset=offset)

    @strawberry.field(description="List attendance records, optionally filtered.")
    def attendance(
        self,
        system: str,
        student_id: Optional[str] = None,
        date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AttendanceType]:
        return resolve_attendance(
            system, student_id=student_id, date=date, limit=limit, offset=offset
        )

    @strawberry.field(description="List enrollment records, optionally filtered.")
    def enrollments(
        self,
        system: str,
        student_id: Optional[str] = None,
        course_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EnrollmentType]:
        return resolve_enrollments(
            system, student_id=student_id, course_id=course_id,
            limit=limit, offset=offset,
        )

    @strawberry.field(description="List timetable slots, optionally filtered by course.")
    def timetable(
        self,
        system: str,
        course_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TimetableType]:
        return resolve_timetable(system, course_id=course_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Root Mutation
# ---------------------------------------------------------------------------

@strawberry.type
class Mutation:
    @strawberry.mutation(description="Create a new student record.")
    def create_student(self, system: str, input: StudentInput) -> StudentType:
        return resolve_create_student(system, input)

    @strawberry.mutation(description="Update an existing student record.")
    def update_student(
        self, system: str, student_id: str, input: StudentInput
    ) -> StudentType:
        return resolve_update_student(system, student_id, input)

    @strawberry.mutation(description="Delete a student record. Returns True on success.")
    def delete_student(self, system: str, student_id: str) -> bool:
        return resolve_delete_student(system, student_id)

    @strawberry.mutation(description="Enroll a student in a course/subject.")
    def create_enrollment(
        self, system: str, student_id: str, course_id: str
    ) -> EnrollmentType:
        return resolve_create_enrollment(system, student_id, course_id)

    @strawberry.mutation(description="Record a grade for a student.")
    def record_grade(self, system: str, input: GradeInput) -> GradeType:
        return resolve_record_grade(system, input)

    @strawberry.mutation(description="Record an attendance entry for a student.")
    def record_attendance(self, system: str, input: AttendanceInput) -> AttendanceType:
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
