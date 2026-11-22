"""The SEND menu catalogue, shared by the GUI sidebar and the CLI.

Each category is one accordion section in the GUI and one numbered sub-menu
in the CLI. Each entry is ``(label, key)``. A key that names a record type
(``core.records.REGISTRY``) opens that type's list page; the others are the
custom pages in :data:`ui.gui.pages.CUSTOM` / the CLI's own handlers.

Keep this as the only list.

The old scaffold had 33 areas and ~230 placeholder buttons; they are folded
into the entries below (e.g. EHCP requests/assessments/drafts/finals/
transfers are stages of one EHCP Tracker record, and attendance, staff,
security and notifications belong to the host school's systems).
"""

from __future__ import annotations

CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Learners", [
        ("SEND Register", "learners"),
        ("School Requests", "school_requests"),
        ("Add Learner", "add_learner"),
        ("Learner Profile", "learner_profile"),
        ("Needs Profile", "needs"),
        ("Parents & Carers", "contacts"),
        ("Learner Voice", "learner_voice"),
        ("Chronology", "chronology"),
    ]),
    ("SEN Support", [
        ("SEN Support Plans", "support_plans"),
        ("Targets & Outcomes", "plan_targets"),
        ("Plan Reviews", "plan_reviews"),
    ]),
    ("EHCP", [
        ("EHCP Tracker", "ehcps"),
        ("Advice & Information", "ehcp_advice"),
        ("Annual Reviews", "annual_reviews"),
        ("Complaints, Mediation & Tribunals", "disputes"),
    ]),
    ("Provision", [
        ("Provision Map", "provision"),
        ("Equipment & Assistive Technology", "equipment"),
        ("Medical & Care Plans", "health_plans"),
    ]),
    ("People & Meetings", [
        ("Professionals Directory", "professionals"),
        ("Referrals & Involvement", "involvement"),
        ("Meetings", "meetings"),
    ]),
    ("Funding & Transitions", [
        ("High Needs Funding", "funding"),
        ("Transitions & Preparing for Adulthood", "transitions"),
    ]),
    ("Reports", [
        ("Due & Overdue", "due_report"),
        ("SEN Register Summary", "register_report"),
        ("EHCP 20-Week Timeliness", "timeliness_report"),
        ("Provision Costs", "costs_report"),
    ]),
    ("System", [
        ("About", "about"),
    ]),
]

#: The sections of a learner's profile (GUI tabs, CLI sub-menu): (label, record type key).
PROFILE_TABS: list[tuple[str, str]] = [
    ("Needs", "needs"),
    ("School requests", "school_requests"),
    ("Support plans", "support_plans"),
    ("Targets", "plan_targets"),
    ("Plan reviews", "plan_reviews"),
    ("EHCP", "ehcps"),
    ("Advice", "ehcp_advice"),
    ("Annual reviews", "annual_reviews"),
    ("Provision", "provision"),
    ("Equipment", "equipment"),
    ("Care plans", "health_plans"),
    ("Parents & carers", "contacts"),
    ("Learner voice", "learner_voice"),
    ("Referrals", "involvement"),
    ("Meetings", "meetings"),
    ("Funding", "funding"),
    ("Transitions", "transitions"),
    ("Complaints & appeals", "disputes"),
]


def load_areas() -> None:
    """Import every area so all record types (and their tables) are registered."""
    from education_system.systems.special_education.modules import (  # noqa: F401
        ehcp, funding, learners, needs, people, provision, reports, requests,
        support_plans,
    )


def all_entries() -> list[tuple[str, str]]:
    return [entry for _cat, items in CATEGORIES for entry in items]
