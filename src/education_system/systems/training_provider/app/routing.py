"""The Training Provider menu catalogue, shared by the GUI sidebar and the CLI.

Each category is one accordion section in the GUI and one numbered sub-menu
in the CLI. Each entry is ``(label, key)``. A key that names a record type
(``core.records.REGISTRY``) opens that type's list page; the others are the
custom pages in :data:`ui.gui.pages.CUSTOM` / the CLI's own handlers.

Keep this as the only list.

The old scaffold (``remove/.../training_provider_system/``) had 471 files of
placeholder screens; what a commercial training provider actually runs is
folded into the entries below: delegates and employer clients, the course
catalogue, trainers and venues, scheduled sessions with bookings and waiting
lists, registers, results and certificates, quality, and invoicing.
"""

from __future__ import annotations

CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Learners", [
        ("Learner Directory", "learners"),
        ("Add Learner", "add_learner"),
        ("Learner Profile", "learner_profile"),
        ("Chronology", "chronology"),
    ]),
    ("Clients", [
        ("Clients", "clients"),
        ("Contracts", "contracts"),
    ]),
    ("Courses & Trainers", [
        ("Course Catalogue", "courses"),
        ("Trainers", "trainers"),
        ("Trainer Approvals", "trainer_approvals"),
        ("Venues", "venues"),
    ]),
    ("Sessions & Bookings", [
        ("Training Requests", "training_requests"),
        ("Sessions", "sessions"),
        ("Bookings", "bookings"),
        ("Take Register", "take_register"),
        ("Attendance Marks", "attendance"),
    ]),
    ("Assessment & Certificates", [
        ("Results", "results"),
        ("Certificates", "certificates"),
        ("Issue Certificates", "issue_certificates"),
    ]),
    ("Progression", [
        ("Progress to Apprenticeship", "apprenticeship_progression"),
        ("Refer to FE College", "refer_to_fe"),
    ]),
    ("Quality", [
        ("Teaching Observations", "observations"),
        ("IQA Sampling", "iqa_samples"),
        ("Feedback & Complaints", "feedback"),
    ]),
    ("Finance", [
        ("Raise Invoices", "raise_invoices"),
        ("Invoices", "invoices"),
        ("Payments", "payments"),
    ]),
    ("Reports", [
        ("Due & Overdue", "due_report"),
        ("Session Fill", "fill_report"),
        ("Bookings Summary", "booking_report"),
        ("Achievement Rates", "achievement_report"),
        ("Expiring Certificates", "expiry_report"),
        ("Aged Debt & Revenue", "debt_report"),
        ("Quality Summary", "quality_report"),
    ]),
    ("System", [
        ("About", "about"),
    ]),
]

#: The sections of a learner's profile (GUI tabs, CLI sub-menu): (label, record type key).
PROFILE_TABS: list[tuple[str, str]] = [
    ("Training requests", "training_requests"),
    ("Bookings", "bookings"),
    ("Attendance", "attendance"),
    ("Results", "results"),
    ("Certificates", "certificates"),
    ("Invoices", "invoices"),
    ("Feedback", "feedback"),
]


def load_areas() -> None:
    """Import every area so all record types (and their tables) are registered."""
    from education_system.systems.training_provider.modules import (  # noqa: F401
        assessment, clients, courses, finance, learners, quality, reports, requests,
        sessions,
    )


def all_entries() -> list[tuple[str, str]]:
    return [entry for _cat, items in CATEGORIES for entry in items]
