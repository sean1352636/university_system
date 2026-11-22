"""The Adult Education menu catalogue, shared by the GUI sidebar and the CLI.

Each category is one accordion section in the GUI and one numbered sub-menu
in the CLI. Each entry is ``(label, key)``. A key that names a record type
(``core.records.REGISTRY``) opens that type's list page; the others are the
custom pages in :data:`ui.gui.pages.CUSTOM` / the CLI's own handlers.

Keep this as the only list.

The old scaffold had 49 areas and ~300 placeholder buttons; they are folded
into the entries below (admissions/onboarding/waiting lists are enquiry and
enrolment statuses, evening/weekend/online classes are class fields, RARPA
is goals + reviews, and so on). Communications, security and integrations
belong to the platform.
"""

from __future__ import annotations

CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Learners", [
        ("Learner Directory", "learners"),
        ("Add Learner", "add_learner"),
        ("Learner Profile", "learner_profile"),
        ("Emergency Contacts", "contacts"),
        ("Identity Checks", "identity_checks"),
        ("Prior Qualifications", "prior_qualifications"),
        ("Chronology", "chronology"),
    ]),
    ("Admissions & Enrolment", [
        ("Enquiries", "enquiries"),
        ("Referrals from FE College", "fe_referrals"),
        ("Funding Eligibility", "eligibility"),
        ("Enrolments", "enrolments"),
        ("Fees & Payments", "payments"),
    ]),
    ("Courses & Classes", [
        ("Course Catalogue", "courses"),
        ("Classes & Timetable", "classes"),
        ("Tutors", "tutors"),
        ("Venues", "venues"),
    ]),
    ("Teaching & Progress", [
        ("Take Register", "take_register"),
        ("Attendance Marks", "attendance"),
        ("Assessments & Results", "assessments"),
        ("Learning Goals", "goals"),
        ("Goal Reviews", "goal_reviews"),
        ("Progression & Destinations", "destinations"),
        ("Refer to FE College", "refer_to_fe"),
        ("University Applications (UCAS)", "university_applications"),
    ]),
    ("Support & Welfare", [
        ("Learning Support", "support_plans"),
        ("Safeguarding Concerns", "safeguarding"),
        ("Feedback & Complaints", "feedback"),
    ]),
    ("Reports", [
        ("Due & Overdue", "due_report"),
        ("Enrolment Summary", "enrolment_report"),
        ("Attendance Report", "attendance_report"),
        ("Funding Summary", "funding_report"),
        ("Fees Outstanding", "fees_report"),
        ("Achievement Rates", "achievement_report"),
        ("Destinations Summary", "destinations_report"),
    ]),
    ("System", [
        ("About", "about"),
    ]),
]

#: The sections of a learner's profile (GUI tabs, CLI sub-menu): (label, record type key).
PROFILE_TABS: list[tuple[str, str]] = [
    ("Enrolments", "enrolments"),
    ("Payments", "payments"),
    ("Attendance", "attendance"),
    ("Assessments", "assessments"),
    ("Funding", "eligibility"),
    ("Goals", "goals"),
    ("Goal reviews", "goal_reviews"),
    ("Prior qualifications", "prior_qualifications"),
    ("Identity", "identity_checks"),
    ("Contacts", "contacts"),
    ("Support", "support_plans"),
    ("Safeguarding", "safeguarding"),
    ("Destinations", "destinations"),
    ("FE referrals", "fe_referrals"),
    ("Feedback", "feedback"),
]


def load_areas() -> None:
    """Import every area so all record types (and their tables) are registered."""
    from education_system.systems.adult_education.modules import (  # noqa: F401
        courses, enrolments, funding, learners, progress, referrals, reports, support,
    )


def all_entries() -> list[tuple[str, str]]:
    return [entry for _cat, items in CATEGORIES for entry in items]
