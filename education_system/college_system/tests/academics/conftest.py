"""Fixtures for academic module tests."""

import pytest

from education_system.college_system.modules.domain.grades.services.grade_service import GradeService
from education_system.college_system.modules.domain.attendance.services.attendance_service import AttendanceService
from education_system.college_system.modules.domain.timetable.services.timetable_service import TimetableService
from education_system.college_system.modules.domain.assignments.services.assignment_service import AssignmentService
from education_system.college_system.modules.domain.timetable.services.room_service import RoomService
from education_system.college_system.modules.domain.markbook.services.markbook_service import MarkbookService
from education_system.college_system.modules.domain.academic_year.services.academic_year_service import AcademicYearService
from education_system.college_system.modules.domain.lesson_plans.services.lesson_plans_service import LessonPlanService
from education_system.college_system.modules.domain.exams.services.exams_service import ExamsService


@pytest.fixture
def grade_service(db_path):
    return GradeService(db_path)


@pytest.fixture
def attendance_service(db_path):
    return AttendanceService(db_path)


@pytest.fixture
def timetable_service(db_path):
    return TimetableService(db_path)


@pytest.fixture
def assignment_service(db_path):
    return AssignmentService(db_path)


@pytest.fixture
def room_service(db_path):
    return RoomService(db_path)


@pytest.fixture
def markbook_service(db_path):
    return MarkbookService(db_path)


@pytest.fixture
def academic_year_service(db_path):
    return AcademicYearService(db_path)


@pytest.fixture
def lesson_plans_service(db_path):
    return LessonPlanService(db_path)


@pytest.fixture
def exams_service(db_path):
    return ExamsService(db_path)
