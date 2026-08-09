"""CLI commands, one module per area.

Every command takes the shared
:class:`~education_system.systems.fe_college.services.session.CollegeSession`
as its only argument and drives it exactly as the GUI windows do, so a rule
enforced in a window is enforced here too:

* :mod:`admin`       dashboards, finance, the account/record join
* :mod:`students`    directory, profiles, enrolment, targets, at-risk
* :mod:`staff`       directory, workload, availability, IV sampling
* :mod:`courses`     catalogue, units, viability, archiving
* :mod:`attendance`  taking registers and reading the rates back
* :mod:`assessments` assignments, marking, verification, results
* :mod:`timetable`   grids, placing sessions, rooms, lesson plans
* :mod:`reports`     running and exporting the reports
"""
