"""Repositories — the only modules that issue SQL against the FE College DB.

Each repository owns one slice of the schema and returns domain objects rather
than rows, so services and interfaces never handle a ``sqlite3.Row``:

* :mod:`student_repository`    learners, enrolments, support plans, targets
* :mod:`staff_repository`      staff, availability, derived workload
* :mod:`course_repository`     courses, units, entry rules, class groups
* :mod:`attendance_repository` register marks and their aggregates
* :mod:`assessment_repository` assignments, submissions, feedback, exams
* :mod:`timetable_repository`  sessions, rooms, bookings, lesson plans
* :mod:`finance_repository`    fees, payments, bursaries, funding
* :mod:`pastoral_repository`   tutorials, behaviour, referrals, wellbeing
"""
