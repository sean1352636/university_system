"""Service layer: the use cases the GUI, CLI and API all call.

One module per area, each composing repositories and domain rules into whole
operations. The interfaces hold no business rules of their own — anything both
a window and a command need lives here, which is what stops the two drifting
apart:

* :mod:`student_service`    learners, profiles, enrolment, targets, at-risk
* :mod:`staff_service`      directory, availability, workload, departments
* :mod:`course_service`     the curriculum offer, units, groups, viability
* :mod:`enrolment_service`  admissions, eligibility, transfers, retention
* :mod:`attendance_service` registers and the rates derived from them
* :mod:`assessment_service` assignments, marking, verification, exams
* :mod:`timetable_service`  sessions, clash checks, rooms, lesson plans
* :mod:`reporting_service`  dashboards and the exports off them

:mod:`session` sits on top of all of them: the signed-in identity plus a façade
over the services, shared by the GUI and the CLI so both resolve "who is this
and what may they see" identically.
"""
