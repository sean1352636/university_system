"""The Secondary School menu catalogue, shared by the GUI and the CLI.

Each category is one accordion section in the GUI sidebar and one numbered
sub-menu in the CLI. Each entry is ``(label, key)``: the GUI opens the page
a feature module registered for ``key`` (``PAGES`` in ``modules/<module>/gui/__init__.py``)
and the CLI runs the menu it registered (``MENUS`` in
``modules/<module>/cli/__init__.py``). An entry with no handler yet shows a
"not built yet" page, so the catalogue doubles as the build map for the
system.

Keep this as the only list - do not copy it into gui_main or cli_main.
"""

from __future__ import annotations

CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Pupil Management", [
        ("Pupil Directory", "pupil_directory"),
        ("Add Pupil", "add_pupil"),
        ("Search Pupils", "search_pupils"),
        ("Pupil Profile", "pupil_profile"),
        ("Admissions", "admissions"),
        ("Year 6 Transition", "year6_transition"),
        ("Enrolment & Leavers", "enrolment"),
        ("Bulk Import", "bulk_import"),
        ("Alumni", "alumni"),
    ]),
    ("Academic Management", [
        ("Academic Year & Calendar", "academic_year"),
        ("Year Groups", "year_groups"),
        ("Form Groups", "form_groups"),
        ("Subjects", "subjects"),
        ("Teaching Groups", "teaching_groups"),
        ("Timetable", "timetable"),
        ("Registers & Attendance", "attendance"),
        ("Lesson Plans", "lesson_plans"),
        ("Cover", "cover"),
        ("Homework", "homework"),
        ("Year 9 Options", "options"),
        ("Enrichment & Clubs", "enrichment"),
        ("Library", "library"),
    ]),
    ("Assessment & Grades", [
        ("Gradebook", "gradebook"),
        ("Assessment Points", "assessment_points"),
        ("Target Grades", "target_grades"),
        ("Mock Exams", "mock_exams"),
        ("Exam Entries", "exam_entries"),
        ("Exam Results", "exam_results"),
        ("Attainment 8 & Progress 8", "headline_measures"),
        ("Interventions", "interventions"),
        ("Reports to Parents", "reports_to_parents"),
    ]),
    ("Pastoral & Wellbeing", [
        ("Form Tutors", "form_tutors"),
        ("Behaviour & Rewards", "behaviour"),
        ("Detentions", "detentions"),
        ("Suspensions & Exclusions", "exclusions"),
        ("Safeguarding", "safeguarding"),
        ("Report a Safeguarding Concern", "report_concern"),
        ("SEND", "send"),
        ("Medical", "medical"),
        ("Pupil Premium", "pupil_premium"),
        ("Attendance Concerns", "attendance_concerns"),
        ("Wellbeing", "wellbeing"),
        ("Complaints", "complaints"),
    ]),
    ("Staff & Communication", [
        ("Staff Portal", "staff_portal"),
        ("Staff Directory", "staff_directory"),
        ("Departments", "departments"),
        ("Staff Absence", "staff_absence"),
        ("Single Central Record", "single_central_record"),
        ("Appraisals & CPD", "appraisals"),
        ("Parent Contacts", "parent_contacts"),
        ("Parents' Evenings", "parents_evenings"),
        ("Email", "messages"),
        ("Announcements", "announcements"),
        ("Letters", "letters"),
    ]),
    ("Finance", [
        ("Trips & Payments", "trips"),
        ("Dinner Money", "dinner_money"),
        ("Expense Claims", "expense_claims"),
        ("Budgets", "budgets"),
        ("My Expense Claims", "my_expense_claims"),
        ("My Budgets", "my_budgets"),
    ]),
    ("Reports & Analytics", [
        ("Attendance Report", "attendance_report"),
        ("Behaviour Report", "behaviour_report"),
        ("Results Analysis", "results_analysis"),
        ("School Census", "census"),
        ("Data Export", "data_export"),
    ]),
    ("Cross-System", [
        ("Student Journey", "student_journey"),
        ("Move to Sixth Form", "move_to_sixth_form"),
        ("Incoming from Primary", "incoming_primary"),
        ("Referrals to Alternative Provision", "ap_referrals"),
        ("SEND Service Requests", "send_requests"),
        ("Local Authority", "local_authority"),
    ]),
    ("System", [
        ("Change Password", "change_password"),
        ("Multi-Factor Authentication", "mfa"),
        ("User Accounts", "user_accounts"),
        ("Settings", "settings"),
        ("Audit Log", "audit_log"),
        ("About", "about"),
    ]),
]


def all_entries() -> list[tuple[str, str]]:
    """Every ``(label, key)`` in catalogue order."""
    return [entry for _cat, items in CATEGORIES for entry in items]
