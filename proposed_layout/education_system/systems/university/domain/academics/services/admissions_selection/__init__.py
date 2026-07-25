"""Grades-gated student admissions selection.

Shared, front-end-agnostic logic for the reworked student-create flow:

* :mod:`tariff`          – A-level grades -> UCAS tariff points
* :mod:`course_catalogue`– live, DB-driven list of available courses
* :mod:`eligibility`     – which courses a tariff qualifies for
* :mod:`curriculum`      – the 18-module (6/year x 3) programme per course
* :mod:`schema`          – idempotent schema + seed
"""

from education_system.systems.university.domain.academics.services.admissions_selection.schema import (
    ensure_selection_schema,
)
from education_system.systems.university.domain.academics.services.admissions_selection.tariff import (
    ALEVEL_POINTS,
    GRADE_CHOICES,
    compute_tariff,
    format_qualifications,
    grade_points,
    normalise_grade,
    prompt_alevels_cli,
)
from education_system.systems.university.domain.academics.services.admissions_selection.course_catalogue import (
    get_course,
    list_active_courses,
)
from education_system.systems.university.domain.academics.services.admissions_selection.eligibility import (
    eligible_courses,
    is_eligible,
)
from education_system.systems.university.domain.academics.services.admissions_selection.curriculum import (
    TOTAL_MODULES,
    enrol_student_in_curriculum,
    get_or_create_curriculum,
)
from education_system.systems.university.domain.academics.services.admissions_selection.module_chat import (
    ensure_module_chat_rooms_and_join,
    purge_student_from_chat,
    purge_user_chat_on_cursor,
    sync_student_module_chat_rooms,
)

__all__ = [
    "ensure_selection_schema",
    "ALEVEL_POINTS",
    "GRADE_CHOICES",
    "compute_tariff",
    "format_qualifications",
    "grade_points",
    "normalise_grade",
    "prompt_alevels_cli",
    "get_course",
    "list_active_courses",
    "eligible_courses",
    "is_eligible",
    "TOTAL_MODULES",
    "enrol_student_in_curriculum",
    "get_or_create_curriculum",
    "ensure_module_chat_rooms_and_join",
    "purge_student_from_chat",
    "purge_user_chat_on_cursor",
    "sync_student_module_chat_rooms",
]
