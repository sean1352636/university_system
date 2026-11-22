"""The Local Authority Education menu catalogue, shared by the GUI sidebar and
the CLI.

Each category is one accordion section in the GUI and one numbered sub-menu
in the CLI. Each entry is ``(label, key)``. A key that names a record type
(``core.records.REGISTRY``) opens that type's list page; the others are the
custom pages in :data:`ui.gui.pages.CUSTOM` / the CLI's own handlers.

Keep this as the only list.

The old scaffold (``remove/.../local_authority_education_system/``) had 13
areas and ~150 placeholder features. They fold into the entries below:
oversubscription/rankings/offers are application fields, waiting lists and
school transfers are in-year applications, educational psychology and
caseworkers belong to EHC assessments, passes/escorts are transport and route
fields. Communications, identity, compliance and integrations belong to the
platform; case management is each area's own status and due dates.
"""

from __future__ import annotations

CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Children & Families", [
        ("Children Directory", "learners"),
        ("Add Child", "add_learner"),
        ("Child Profile", "learner_profile"),
        ("Parents & Carers", "contacts"),
        ("Chronology", "chronology"),
    ]),
    ("Schools", [
        ("Schools Register", "schools"),
        ("School Notifications", "school_notifications"),
    ]),
    ("Admissions", [
        ("Applications & Offers", "applications"),
        ("Admission Appeals", "appeals"),
        ("Fair Access Panel", "fair_access"),
    ]),
    ("Attendance & Welfare", [
        ("Attendance Cases", "attendance_cases"),
        ("Penalty Notices", "penalty_notices"),
        ("Children Missing Education", "cme"),
        ("Elective Home Education", "ehe"),
    ]),
    ("Exclusions", [
        ("Suspensions & Exclusions", "exclusions"),
    ]),
    ("SEND", [
        ("EHC Needs Assessments", "ehc_requests"),
        ("EHC Plans", "ehc_plans"),
        ("SEND Tribunal Appeals", "tribunals"),
        ("High Needs Top-ups", "topups"),
    ]),
    ("Transport", [
        ("Transport Applications", "transport"),
        ("Transport Routes", "routes"),
    ]),
    ("Reports", [
        ("Due & Overdue", "due_report"),
        ("Admissions Summary", "admissions_report"),
        ("School Places", "places_report"),
        ("Attendance & Welfare", "welfare_report"),
        ("Exclusions Summary", "exclusions_report"),
        ("SEND Summary", "send_report"),
        ("Transport Costs", "transport_report"),
    ]),
    ("System", [
        ("About", "about"),
    ]),
]

#: The sections of a child's profile (GUI tabs, CLI sub-menu): (label, record type key).
PROFILE_TABS: list[tuple[str, str]] = [
    ("Parents & carers", "contacts"),
    ("Admissions", "applications"),
    ("Appeals", "appeals"),
    ("Fair access", "fair_access"),
    ("Attendance", "attendance_cases"),
    ("Penalty notices", "penalty_notices"),
    ("Missing education", "cme"),
    ("Home education", "ehe"),
    ("Exclusions", "exclusions"),
    ("EHC assessments", "ehc_requests"),
    ("EHC plans", "ehc_plans"),
    ("Tribunals", "tribunals"),
    ("Top-ups", "topups"),
    ("Transport", "transport"),
]


def load_areas() -> None:
    """Import every area so all record types (and their tables) are registered."""
    from education_system.systems.local_authority.modules import (  # noqa: F401
        admissions, children, exclusions, reports, schools, send, transport, welfare,
    )


def all_entries() -> list[tuple[str, str]]:
    return [entry for _cat, items in CATEGORIES for entry in items]
