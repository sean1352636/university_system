"""Strawberry GraphQL type definitions for core education system entities."""

from __future__ import annotations

from typing import Optional

import strawberry


@strawberry.type
class StudentType:
    id: int
    student_id: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    date_of_birth: Optional[str]
    enrollment_date: Optional[str]
    # college/university = "major"; school/primary = "course"/"class"
    major: Optional[str]
    status: Optional[str]
    gpa: Optional[float]
    system_key: str


@strawberry.type
class CourseType:
    id: int
    course_code: Optional[str]
    course_name: str
    description: Optional[str]
    credits: Optional[int]
    department: Optional[str]
    instructor: Optional[str]
    max_enrollment: Optional[int]
    current_enrollment: Optional[int]
    semester: Optional[str]
    status: Optional[str]


@strawberry.type
class GradeType:
    id: int
    student_id: str
    course_id: Optional[str]
    assignment_name: Optional[str]
    score: Optional[float]
    max_score: Optional[float]
    letter_grade: Optional[str]
    grade_date: Optional[str]


@strawberry.type
class AttendanceType:
    id: int
    student_id: str
    course_id: Optional[str]
    date: Optional[str]
    status: Optional[str]
    notes: Optional[str]


@strawberry.type
class EnrollmentType:
    id: int
    student_id: str
    course_id: str
    enrollment_date: Optional[str]
    status: Optional[str]
    grade: Optional[str]


@strawberry.type
class UserType:
    id: int
    username: str
    email: Optional[str]
    role: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    system_key: str


@strawberry.type
class TimetableType:
    id: int
    course_id: Optional[str]
    day_of_week: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    room: Optional[str]
    instructor: Optional[str]
