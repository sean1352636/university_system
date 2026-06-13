# University Domain Modules

The university system keeps broad ownership areas at the top level, such as
`academics`, `student_affairs`, `commerce`, `finance`, `health`, and `staff_hr`.
Some API route names are narrower than those top-level domains. Stable,
university-essential capabilities can also have first-class facade packages
that delegate to the existing implementation.

## First-Class Academic Capability Facades

These packages are import-stable entry points for university capabilities that
previously lived only under nested `academics/services` or `academics/gui`
paths:

| Domain package | Backing implementation |
| --- | --- |
| `academic_integrity` | `academics/services/plagiarism`, `academics/gui/plagiarism_main_gui` |
| `calendar` | `academics/services/academic_calendar`, `academics/gui/academic_calendar` |
| `degree_audit` | `academics/services/degree_audit` |
| `library` | `academics/services/library`, `academics/gui/library` |
| `office_hours` | `academics/services/office_hours`, `academics/gui/office_hours` |
| `student_lifecycle` | admissions, student records, student affairs, career services, and alumni |
| `virtual_classroom` | `academics/services/virtual_classroom` |

## Student Lifecycle Ownership

Use `student_lifecycle` as the canonical map for the whole student-to-alumni
journey. It keeps the operational stages explicit while preserving the focused
domain owners:

| Stage | Owner |
| --- | --- |
| Prospect and applicant | `admissions/services` |
| Enrolled student | `modules/shared/gui/main/students` |
| Student services | `student_affairs` |
| Career readiness | `career/services` |
| Alumni engagement | `career/alumni`, backed by `student_affairs/services/alumni_management` |

## API Route Ownership

| API route area | Current domain owner |
| --- | --- |
| `absence` | `academics/services/attendance/absence_tracking` |
| `assessment` | `academics/services/assignments` and assessment tables |
| `calendar` | `calendar` |
| `club` | `student_affairs/student_union/clubs` |
| `credential` | `finance/blockchain`, `student_affairs/achievement_badges`, and certificate helpers |
| `degree` | `degree_audit` and `academics/services/course_management` |
| `dining` | `commerce/services` until a dedicated dining service is extracted |
| `emergency` | DB-first API backed by health, wellness, housing, mobility, and staff emergency data |
| `library` | `library` |
| `lms` | `academics/services/lms` and shared LMS helpers |
| `office_hours` | `office_hours` |
| `parent` | `academics/services/parent_portal`, `academics/gui/parent_portal`, and shared parent portal API helpers |
| `ta` | `academics/services/assignments/admin_tools` |
| `tutoring` | `student_affairs/services` and student support workflows |
| `virtual_classroom` | `virtual_classroom` |

## Promotion Rule

Create a new top-level domain module only when a feature needs its own service
layer, GUI/CLI entry points, schema ownership, tests, and operational lifecycle.
If a route is a thin API facade over an existing service, keep it under the
existing domain owner and add the route-to-owner mapping here.

See `IMPLEMENTATION_STATUS.md` for resolved and intentionally deferred
placeholder-backed areas.
