"""The Alternative Provision menu catalogue, shared by the GUI sidebar and the CLI.

Each category is one accordion section in the GUI and one numbered sub-menu
in the CLI. Each entry is ``(label, key)``. A key that names a record type
(``core.records.REGISTRY``) opens that type's list page; the others are the
custom pages in :data:`ui.gui.pages.CUSTOM` / the CLI's own handlers.

Keep this as the only list.

The old scaffold had 31 areas and ~210 placeholder buttons; they are folded
into the entries below (triage, waiting lists and decisions are referral
statuses; dual registration, timetables and commissioning are placement
fields; restorative practice and positive behaviour are incident actions and
plans; and so on). Communications, security and integrations belong to the
platform.
"""

from __future__ import annotations

CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Pupils", [
        ("Pupil Directory", "learners"),
        ("Add Pupil", "add_learner"),
        ("Pupil Profile", "learner_profile"),
        ("Parents, Carers & Contacts", "contacts"),
        ("Chronology", "chronology"),
    ]),
    ("Referrals & Placements", [
        ("Referrals", "referrals"),
        ("Risk Assessments", "risk_assessments"),
        ("Placements", "placements"),
        ("Placement Reviews", "placement_reviews"),
        ("Provider Directory", "providers"),
    ]),
    ("Attendance", [
        ("Take Register", "take_register"),
        ("Attendance Marks", "attendance"),
    ]),
    ("Teaching & Progress", [
        ("Learning & Support Plans", "plans"),
        ("Baseline & Progress", "progress"),
        ("Qualifications & Exams", "qualifications"),
        ("Wellbeing Interventions", "interventions"),
    ]),
    ("Behaviour & Safeguarding", [
        ("Behaviour Incidents", "incidents"),
        ("Suspensions & Exclusions", "suspensions"),
        ("Safeguarding Concerns", "safeguarding"),
        ("Missing Episodes", "missing_episodes"),
        ("Professionals Involved", "professionals"),
    ]),
    ("Moving On", [
        ("Reintegration Plans", "reintegration"),
        ("Destinations", "destinations"),
    ]),
    ("Commissioning", [
        ("Invoices", "invoices"),
        ("Placement Costs", "costs_report"),
    ]),
    ("Reports", [
        ("Due & Overdue", "due_report"),
        ("Roll Summary", "roll_report"),
        ("Attendance Report", "attendance_report"),
        ("Behaviour Summary", "behaviour_report"),
        ("Outcomes", "outcomes_report"),
    ]),
    ("System", [
        ("About", "about"),
    ]),
]

#: The sections of a pupil's profile (GUI tabs, CLI sub-menu): (label, record type key).
PROFILE_TABS: list[tuple[str, str]] = [
    ("Referrals", "referrals"),
    ("Placements", "placements"),
    ("Reviews", "placement_reviews"),
    ("Attendance", "attendance"),
    ("Risk", "risk_assessments"),
    ("Plans", "plans"),
    ("Progress", "progress"),
    ("Qualifications", "qualifications"),
    ("Interventions", "interventions"),
    ("Incidents", "incidents"),
    ("Suspensions", "suspensions"),
    ("Safeguarding", "safeguarding"),
    ("Missing", "missing_episodes"),
    ("Professionals", "professionals"),
    ("Contacts", "contacts"),
    ("Reintegration", "reintegration"),
    ("Destinations", "destinations"),
    ("Invoices", "invoices"),
]


def load_areas() -> None:
    """Import every area so all record types (and their tables) are registered."""
    from education_system.systems.alternative_provision.modules import (  # noqa: F401
        attendance, behaviour, commissioning, learners, learning, placements, referrals,
        reintegration, reports, safeguarding,
    )


def all_entries() -> list[tuple[str, str]]:
    return [entry for _cat, items in CATEGORIES for entry in items]
