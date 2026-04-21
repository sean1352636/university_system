"""Role-scoped Course Management portals.

The admin-facing ``CourseManagementGUI`` in
``course_management_gui/core/main_gui.py`` stays available for users
with administrative roles; these smaller portals expose only what each
role needs day-to-day:

- ``CourseManagementStudentPortal`` — read-only view of the student's
  enrolled modules + optional catalogue browser.
- ``CourseManagementInstructorPortal`` — the modules the instructor
  teaches plus their student rosters.
- ``CourseManagementStaffPortal`` — read-only browse/filter across all
  modules with roster drill-down (no create/edit/delete).
"""

from education_system.university_system.modules.domain.academics.gui.course_management.student_portal import (
    CourseManagementStudentPortal,
    launch_course_management_student_portal,
)
from education_system.university_system.modules.domain.academics.gui.course_management.instructor_portal import (
    CourseManagementInstructorPortal,
    launch_course_management_instructor_portal,
)
from education_system.university_system.modules.domain.academics.gui.course_management.staff_portal import (
    CourseManagementStaffPortal,
    launch_course_management_staff_portal,
)

__all__ = [
    "CourseManagementStudentPortal",
    "CourseManagementInstructorPortal",
    "CourseManagementStaffPortal",
    "launch_course_management_student_portal",
    "launch_course_management_instructor_portal",
    "launch_course_management_staff_portal",
]
