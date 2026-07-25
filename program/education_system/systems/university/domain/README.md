# University Domain Modules

The university system keeps broad ownership areas at the top level:
`academics`, `admissions`, `analytics`, `campus`, `commerce`, `finance`,
`health`, `operations` (which owns `staff_hr`), and `student_affairs`. Some API
route names are narrower than those top-level domains; the mapping below records
which existing domain owns each route.

## Student Lifecycle Ownership

The whole student-to-alumni journey spans several domains. This table is the
canonical map of the operational stages to their owning module:

| Stage | Owner |
| --- | --- |
| Prospect and applicant | `admissions/services` |
| Enrolled student | `modules/shared/gui/main/students` |
| Student services | `student_affairs` |
| Career readiness | `student_affairs/services/career_services` |
| Alumni engagement | `student_affairs/services/alumni_management` |

## API Route Ownership

Route names do not always match a top-level domain folder. Each route is a thin
API facade over an existing service; this table names the real owner.

| API route area | Current domain owner |
| --- | --- |
| `absence` | `academics/services/attendance/absence_tracking` |
| `assessment` | `academics/services/assignments` and assessment tables |
| `calendar` | `academics/services/academic_calendar`, `academics/gui/academic_calendar` |
| `club` | `student_affairs/student_union/clubs` |
| `credential` | `finance/blockchain`, `student_affairs/achievement_badges`, and certificate helpers |
| `degree` | `academics/services/degree_audit` and `academics/services/course_management` |
| `dining` | `commerce/services` until a dedicated dining service is extracted |
| `emergency` | DB-first API backed by health, wellness, housing, mobility, and staff emergency data |
| `library` | `academics/services/library`, `academics/gui/library` |
| `lms` | `academics/services/lms` and shared LMS helpers |
| `office_hours` | `academics/services/office_hours`, `academics/gui/office_hours` |
| `parent` | `academics/services/parent_portal`, `academics/gui/parent_portal`, and shared parent portal API helpers |
| `ta` | `academics/services/assignments/admin_tools` |
| `tutoring` | `student_affairs/services` and student support workflows |
| `virtual_classroom` | `academics/services/virtual_classroom` |

## Promotion Rule

Create a new top-level domain module only when a feature needs its own service
layer, GUI/CLI entry points, schema ownership, tests, and operational lifecycle.
If a route is a thin API facade over an existing service, keep it under the
existing domain owner and add the route-to-owner mapping above.
