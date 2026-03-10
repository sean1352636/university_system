"""API route blueprints for the Secondary School system."""

from education_system.secondary_school.api.routes.auth_routes import auth_bp, init_auth_routes
from education_system.secondary_school.api.routes.student_routes import student_bp, init_student_routes
from education_system.secondary_school.api.routes.subject_routes import subject_bp, init_subject_routes
from education_system.secondary_school.api.routes.enrollment_routes import enrollment_bp, init_enrollment_routes
from education_system.secondary_school.api.routes.grade_routes import grade_bp, init_grade_routes
from education_system.secondary_school.api.routes.attendance_routes import attendance_bp, init_attendance_routes
from education_system.secondary_school.api.routes.behaviour_routes import behaviour_bp, init_behaviour_routes
from education_system.secondary_school.api.routes.system_routes import system_bp, init_system_routes

ALL_BLUEPRINTS = [
    auth_bp, student_bp, subject_bp, enrollment_bp, grade_bp,
    attendance_bp, behaviour_bp, system_bp,
]

ALL_INIT_FUNCS = [
    init_auth_routes, init_student_routes, init_subject_routes,
    init_enrollment_routes, init_grade_routes, init_attendance_routes,
    init_behaviour_routes, init_system_routes,
]
