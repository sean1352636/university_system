"""Prompt + print helpers for the Sixth Form Alumni CLI.

Split out of ``alumni_cli`` (2026-10-22); that module re-exports every name.
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.learners.alumni import records as alumni_records
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.learners.alumni.models import (
    ACHIEVEMENT_CATEGORIES,
    Alumnus,
    CAMPAIGN_STATUSES,
    APPLICATION_STATUSES,
    BEQUEST_STATUSES,
    CUSTOM_FIELD_TYPES,
    ERASURE_STATUSES,
    WEBHOOK_EVENT_TYPES,
    CHAPTER_ROLES,
    CONNECTION_KINDS,
    DIRECTORY_CONSENT_SCOPE,
    DONOR_STAGES,
    DRIP_STATUSES,
    JOB_STATUSES,
    JOB_TYPES,
    NEET_STATUSES,
    NEWSLETTER_STATUSES,
    PROFICIENCY_LEVELS,
    RECURRING_FREQS,
    RECURRING_STATUSES,
    SAFEGUARDING_STATUSES,
    SOCIAL_PLATFORMS,
    TRACK_KINDS,
    CONSENT_SCOPES,
    DEFAULT_CAMPAIGN_STATUS,
    DEFAULT_DESTINATION,
    DEFAULT_EDUCATION_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_LEAVING_REASON,
    DEFAULT_PLEDGE_STATUS,
    DEFAULT_RSVP_STATUS,
    DEFAULT_STATUS,
    DESTINATION_TYPES,
    EDUCATION_STATUSES,
    EMAIL_LABELS,
    EVENT_STATUSES,
    EVENT_TYPES,
    GENDER_OPTIONS,
    LEAVING_REASONS,
    MENTORSHIP_STATUSES,
    PAYMENT_METHODS,
    PHONE_LABELS,
    PLEDGE_STATUSES,
    REFERENCE_TYPES,
    RSVP_STATUSES,
    SALARY_BANDS,
    SECTORS,
    SESSION_FORMATS,
    STATUSES,
    VOLUNTEER_ACTIVITY_TYPES,
    WORK_EXP_STATUSES,
)
from education_system.systems.sixth_form.domain.learners.alumni.integrations import MEDIA_KINDS
from education_system.systems.sixth_form.domain.learners.alumni.compliance import PROTECTED_CHARS
from education_system.systems.sixth_form.domain.learners.alumni.engagement import (
    CHAPTER_KINDS,
    MILESTONE_KINDS,
)
from education_system.systems.sixth_form.domain.learners.alumni.comms import (
    COMM_CHANNELS,
    COMM_STATUSES,
)
from education_system.systems.sixth_form.domain.learners.alumni.db import ValidationError

logger = logging.getLogger(
    "education_system.systems.sixth_form.interfaces.cli.learners.alumni.alumni_cli")


class _UserAbort(Exception):
    pass



# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_alumnus() -> Alumnus:
    rows = alumni_records.list_alumni()
    if not rows:
        print("    No alumni.")
        raise _UserAbort
    print("\n  Alumni:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.alumni_id}  {a.full_name[:24]:<24}  "
              f"({a.leaving_year or '—'})  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or alumni id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((a for a in rows if a.alumni_id == n), None)
            if match:
                return match
        print("    No matching alumnus.")


def _pick_student() -> str:
    rows = student_data.list_students()
    if not rows:
        print("    No current students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
            continue
        match = next((s for s in rows
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_alumni(rows: list[Alumnus]) -> None:
    if not rows:
        print("\n  (no alumni)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<24}  {'Year':<6}  "
          f"{'Destination':<14}  {'Detail':<28}  Status")
    print("  " + "-" * 95)
    for a in rows:
        print(f"  {a.alumni_id:>4}  {a.full_name[:24]:<24}  "
              f"{a.leaving_year or '—':<6}  "
              f"{a.destination_type[:14]:<14}  "
              f"{(a.destination_detail or '—')[:28]:<28}  "
              f"{a.status}")
    print(f"\n  {len(rows)} alumnus/alumni.")
