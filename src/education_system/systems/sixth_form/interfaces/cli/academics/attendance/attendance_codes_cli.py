"""CLI flows for attendance mark codes, reasons, authorisation and audit.

Submenu hung off Attendance, covering the four data modules that sit
behind the register: :mod:`attendance_codes` (the vocabulary),
:mod:`attendance_authorisation` (who signed an absence off, and where an
off-site learner was), and :mod:`attendance_audit` (the amendment trail
and voided rows).
"""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _timedelta
from typing import Callable

from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.academics.attendance.attendance_cli import (
    lazy_domain,
    _input,
    _pause,
    _pick_from,
    _pick_group,
    _UserAbort,
)

# Domain modules load on first use (see attendance_cli.lazy_domain).
data = lazy_domain("attendance")
audit = lazy_domain("attendance_audit")
authz = lazy_domain("attendance_authorisation")
codes = lazy_domain("attendance_codes")

logger = logging.getLogger(__name__)

# Default reporting window for the listings below.
_WINDOW_DAYS: int = 28


def _today() -> str:
    return _date.today().isoformat()


def _window() -> tuple[str, str]:
    """Prompt for a date window, defaulting to the last four weeks."""
    default_from = (_date.today() - _timedelta(days=_WINDOW_DAYS)).isoformat()
    date_from = _input("From (YYYY-MM-DD)", default=default_from)
    date_to = _input("To (YYYY-MM-DD)", default=_today())
    return date_from, date_to


def _pick_code(*, only: tuple[str, ...] | None = None,
               default: str | None = None) -> str:
    """List the mark codes and take a letter or a row number."""
    marks = [m for m in codes.MARK_CODES
             if only is None or m.code in only]
    print("\n  Mark codes:")
    for i, mark in enumerate(marks, 1):
        print(f"    {i:>3}) {mark.code:<2}  {mark.label:<38} "
              f"{mark.meaning}")
    while True:
        raw = _input(f"Pick #1..{len(marks)} or a code", default=default or "")
        if raw.isdigit() and 1 <= int(raw) <= len(marks):
            return marks[int(raw) - 1].code
        match = next((m for m in marks if m.code == raw.strip()), None)
        if match:
            return match.code
        print("    Not one of the codes listed.")


def _pick_reason(*, allow_none: bool = True) -> int | None:
    reasons = codes.list_reasons()
    if not reasons:
        print("    No absence reasons configured.")
        return None
    print("\n  Absence reasons:")
    for i, reason in enumerate(reasons, 1):
        code = f"[{reason.default_code}]" if reason.default_code else "[  ]"
        print(f"    {i:>3}) {code} {reason.name:<28} {reason.category}")
    prompt = ("Pick #1..%d%s" % (len(reasons),
                                 " (blank for none)" if allow_none else ""))
    while True:
        raw = _input(prompt)
        if not raw and allow_none:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(reasons):
            return reasons[int(raw) - 1].reason_id
        print("    Out of range.")


def _pick_record_id(label: str = "Record ID") -> int:
    raw = _input(label, allow_empty=False)
    if not raw.isdigit():
        print("    Record ID must be a whole number.")
        raise _UserAbort
    return int(raw)


# ── Mark codes ──────────────────────────────────────────────────────

def show_codes() -> None:
    print("\n═══ Statutory Mark Codes ═══")
    for meaning in codes.MEANINGS:
        marks = codes.codes_for_meaning(meaning)
        if not marks:
            continue
        print(f"\n  {meaning}:")
        for mark in marks:
            print(f"    {mark.code:<2}  {mark.label:<40} → {mark.status}")
            print(f"        {mark.description}")
    print("\n  Attending = Present + Approved. 'Not counted' codes drop out")
    print("  of the denominator entirely rather than counting as absence.")
    _pause()


def code_report() -> None:
    print("\n═══ Code Breakdown ═══")
    date_from, date_to = _window()
    group_id = None
    if _input("Limit to one group? (y/N)", default="n").lower().startswith("y"):
        group_id = _pick_group()
    try:
        rows = codes.code_breakdown(group_id=group_id, date_from=date_from,
                                    date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  No attendance recorded in that window.")
        _pause()
        return

    total = sum(r.count for r in rows)
    print(f"\n  {total} mark(s) between {date_from} and {date_to}:\n")
    print(f"    {'Code':<6}{'Label':<40}{'Meaning':<14}{'Count':>7}{'%':>8}")
    for row in rows:
        share = 100.0 * row.count / total if total else 0.0
        print(f"    {row.code or '—':<6}{row.label:<40}{row.meaning:<14}"
              f"{row.count:>7}{share:>7.1f}%")

    meanings = codes.meaning_breakdown(group_id=group_id, date_from=date_from,
                                       date_to=date_to)
    attending = meanings[codes.PRESENT] + meanings[codes.APPROVED]
    possible = total - meanings[codes.NOT_COUNTED]
    if possible:
        print(f"\n  Attending {attending}/{possible} = "
              f"{100.0 * attending / possible:.1f}%")

    sources = codes.source_breakdown(group_id=group_id, date_from=date_from,
                                     date_to=date_to)
    if sources:
        print("\n  By source: " + ", ".join(
            f"{k} {v}" for k, v in sources.items()))
    _pause()


def backfill() -> None:
    print("\n═══ Backfill Mark Codes ═══")
    print("\n  Rows written before codes existed carry a status but no code.")
    print("  Backfilling maps each status to its default code — every")
    print("  uncoded absence becomes N ('no reason yet provided'), never O.")
    outstanding = codes.uncoded_count()
    print(f"\n  {outstanding} live row(s) currently have no code.")
    if not outstanding:
        _pause()
        return
    if not _input("Backfill them now? (y/N)",
                  default="n").lower().startswith("y"):
        print("  Cancelled.")
        return
    touched = codes.backfill_codes()
    print(f"\n  ✓ Coded {touched} row(s).")
    _pause()


def recode_record() -> None:
    print("\n═══ Recode a Record ═══")
    record_id = _pick_record_id()
    record = data.get_record(record_id)
    if record is None:
        print(f"\n  ✗ No record with id {record_id}.")
        _pause()
        return
    print(f"\n  {record.student_id} on {record.date}: "
          f"{record.status} [{record.code or 'no code'}]")
    code = _pick_code(default=record.code or "")
    reason_id = _pick_reason()
    note = _input("Note (optional)")
    try:
        out = codes.set_code(record_id, code, reason_id=reason_id,
                             actor=_input("Your username", default="cli"),
                             note=note or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Now {out.status} [{out.code}].")
    _pause()


# ── Absence reasons ─────────────────────────────────────────────────

def list_reasons() -> None:
    print("\n═══ Absence Reasons ═══")
    include_archived = _input(
        "Include archived? (y/N)", default="n").lower().startswith("y")
    reasons = codes.list_reasons(active_only=not include_archived)
    if not reasons:
        print("\n  None configured.")
        _pause()
        return
    print(f"\n    {'ID':>4}  {'Name':<28}{'Category':<14}{'Code':<6}"
          f"{'Evidence':<10}{'Used':>6}  Status")
    for reason in reasons:
        print(f"    {reason.reason_id:>4}  {reason.name:<28}"
              f"{reason.category:<14}{reason.default_code or '—':<6}"
              f"{'yes' if reason.requires_evidence else 'no':<10}"
              f"{codes.reason_usage(reason.reason_id):>6}  "
              f"{'active' if reason.active else 'archived'}")
    _pause()


def add_reason() -> None:
    print("\n═══ Add Absence Reason ═══")
    name = _input("Name", allow_empty=False)
    category = _pick_from("Category", list(codes.REASON_CATEGORIES),
                          default=codes.DEFAULT_REASON_CATEGORY)
    use_code = _input("Give it a default mark code? (y/N)",
                      default="n").lower().startswith("y")
    default_code = _pick_code() if use_code else None
    evidence = _input("Requires evidence? (y/N)",
                      default="n").lower().startswith("y")
    try:
        reason = codes.create_reason({
            "name": name, "category": category,
            "default_code": default_code,
            "requires_evidence": evidence,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created reason #{reason.reason_id} ({reason.name}).")
    _pause()


def archive_reason() -> None:
    print("\n═══ Archive Absence Reason ═══")
    print("\n  Archiving hides a reason from the pickers without deleting")
    print("  it, so historic rows keep pointing at something meaningful.")
    reason_id = _pick_reason(allow_none=False)
    if reason_id is None:
        return
    used = codes.reason_usage(reason_id)
    if used:
        print(f"\n  {used} live row(s) use this reason. They keep it.")
    try:
        reason = codes.archive_reason(reason_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Archived {reason.name}.")
    _pause()


# ── Authorisation ───────────────────────────────────────────────────

def authorisation_queue() -> None:
    print("\n═══ Absences Awaiting a Decision ═══")
    date_from, date_to = _window()
    stale_only = _input(
        f"Only those waiting {authz.STALE_AFTER_DAYS}+ days? (y/N)",
        default="n").lower().startswith("y")
    try:
        rows = authz.pending(date_from=date_from, date_to=date_to,
                             stale_only=stale_only)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  ✓ Nothing waiting — every absence has been decided.")
        _pause()
        return

    print(f"\n  {len(rows)} absence(s) with no decision:\n")
    print(f"    {'Rec':>5}  {'Date':<12}{'Student':<26}{'Code':<6}"
          f"{'Waiting':>8}  Reason")
    for row in rows:
        flag = " !" if row.stale else ""
        print(f"    {row.record_id:>5}  {row.record.date:<12}"
              f"{row.student_name[:25]:<26}{row.record.code or '—':<6}"
              f"{row.days_waiting:>6}d{flag}  {row.reason_name or ''}")
    stale = sum(1 for r in rows if r.stale)
    if stale:
        print(f"\n  {stale} marked ! have been waiting "
              f"{authz.STALE_AFTER_DAYS} days or more.")
    _pause()


def authorise_absence() -> None:
    print("\n═══ Authorise an Absence ═══")
    record_id = _pick_record_id()
    record = data.get_record(record_id)
    if record is None:
        print(f"\n  ✗ No record with id {record_id}.")
        _pause()
        return
    print(f"\n  {record.student_id} on {record.date}: "
          f"{record.status} [{record.code or 'no code'}]")
    reason_id = _pick_reason()
    suggested = codes.suggest_code(reason_id) if reason_id else None
    if suggested:
        print(f"\n  That reason is normally recorded as "
              f"{codes.describe(suggested)}")
    code = None
    if _input("Choose a different code? (y/N)",
              default="n").lower().startswith("y"):
        code = _pick_code(only=authz.AUTHORISABLE_CODES)
    who = _input("Authorised by (username)", allow_empty=False)
    note = _input("Grounds / note (optional)")
    try:
        out = authz.authorise(record_id, authorised_by=who, code=code,
                              reason_id=reason_id, note=note or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Authorised as [{out.code}] by {out.authorised_by} "
          f"at {out.authorised_at}.")
    _pause()


def authorise_window() -> None:
    print("\n═══ Authorise a Learner's Absences Over a Range ═══")
    print("\n  The hospital-admission case: one decision covering every")
    print("  lesson the learner missed.")
    student_id = _input("Student ID", allow_empty=False)
    date_from, date_to = _window()
    reason_id = _pick_reason()
    who = _input("Authorised by (username)", allow_empty=False)
    note = _input("Grounds / note (optional)")
    try:
        result = authz.authorise_range(
            student_id, date_from=date_from, date_to=date_to,
            authorised_by=who, reason_id=reason_id, note=note or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  {result.message}")
    for failure in (result.failures or [])[:10]:
        print(f"    · {failure}")
    _pause()


def withdraw_authorisation() -> None:
    print("\n═══ Withdraw an Authorisation ═══")
    record_id = _pick_record_id()
    print("\n  Recode to O (unauthorised — the decision was 'no') or")
    print("  N (undecided — put it back in the queue).")
    code = _pick_from("New code", ["O", "N"], default="O")
    reason = _input("Why (optional)")
    try:
        out = authz.unauthorise(record_id, actor=_input(
            "Your username", default="cli"), reason=reason or None, code=code)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Now {out.status} [{out.code}], authorisation cleared.")
    _pause()


def who_authorises() -> None:
    print("\n═══ Authorisations by Staff Member ═══")
    date_from, date_to = _window()
    rows = authz.authorised_by_staff(date_from=date_from, date_to=date_to)
    if not rows:
        print("\n  No authorisations in that window.")
        _pause()
        return
    total = sum(rows.values())
    print(f"\n  {total} authorisation(s):\n")
    for who, count in rows.items():
        share = 100.0 * count / total
        print(f"    {who:<24}{count:>6}{share:>8.1f}%")
    top = max(rows.values())
    if total and top / total > 0.8:
        print("\n  One account accounts for over 80% of these — worth")
        print("  checking it is not a shared login.")
    _pause()


# ── Off-site placement ──────────────────────────────────────────────

def mark_offsite() -> None:
    print("\n═══ Mark a Learner Off Site ═══")
    print("\n  For a learner who was elsewhere but still in education —")
    print("  work placement, partner college, trip. Approved-activity")
    print("  codes count as attending, so this does not dent their %.")
    record_id = _pick_record_id()
    kind = _pick_from("Placement", [*authz.OFFSITE_KINDS, "Other"],
                      default="Work placement")
    location = (_input("Location / employer", allow_empty=False)
                if kind == "Other" else
                _input("Location / employer", default=kind))
    suggested = authz.suggest_offsite_code(kind)
    print(f"\n  Suggested code: {codes.describe(suggested)}")
    code = (suggested if _input("Use it? (Y/n)", default="y")
            .lower().startswith("y") else _pick_code())
    try:
        out = authz.set_offsite(record_id, location=location, code=code,
                                actor=_input("Your username", default="cli"))
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {out.student_id} recorded at {out.offsite_location} "
          f"[{out.code}].")
    _pause()


def offsite_register() -> None:
    print("\n═══ Off-Site Placement Register ═══")
    date_from, date_to = _window()
    rows = authz.list_offsite(date_from=date_from, date_to=date_to)
    if not rows:
        print("\n  No off-site marks in that window.")
        _pause()
        return
    print(f"\n  {len(rows)} placement mark(s):\n")
    print(f"    {'Rec':>5}  {'Date':<12}{'Student':<26}{'Code':<6}Location")
    for row in rows:
        print(f"    {row.record.record_id:>5}  {row.record.date:<12}"
              f"{row.student_name[:25]:<26}{row.code:<6}{row.location}")
    breakdown = authz.offsite_breakdown(date_from=date_from, date_to=date_to)
    print("\n  By location: " + ", ".join(
        f"{k} ({v})" for k, v in breakdown.items()))
    _pause()


# ── Voiding ─────────────────────────────────────────────────────────

def void_record() -> None:
    print("\n═══ Void a Record ═══")
    print("\n  A void keeps the row for audit but drops it from every")
    print("  count. Prefer this to deleting anything that was ever real.")
    record_id = _pick_record_id()
    record = data.get_record(record_id)
    if record is None:
        print(f"\n  ✗ No record with id {record_id}.")
        _pause()
        return
    print(f"\n  {record.student_id} on {record.date}: "
          f"{record.status} [{record.code or 'no code'}]")
    reason = _input("Why is this being voided?", allow_empty=False)
    try:
        audit.void_record(record_id, reason=reason,
                          actor=_input("Your username", default="cli"))
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Record #{record_id} voided.")
    _pause()


def voided_records() -> None:
    print("\n═══ Voided Records ═══")
    date_from, date_to = _window()
    rows = audit.list_voided(date_from=date_from, date_to=date_to)
    if not rows:
        print("\n  None in that window.")
        _pause()
        return
    print(f"\n  {len(rows)} voided row(s):\n")
    print(f"    {'Rec':>5}  {'Date':<12}{'Student':<14}{'Was':<12}"
          f"{'By':<14}Reason")
    for record in rows:
        print(f"    {record.record_id:>5}  {record.date:<12}"
              f"{record.student_id:<14}{record.status:<12}"
              f"{(record.voided_by or '—'):<14}{record.void_reason or ''}")
    if _input("\n  Restore one? (y/N)", default="n").lower().startswith("y"):
        record_id = _pick_record_id()
        try:
            audit.restore_record(record_id,
                                 actor=_input("Your username", default="cli"))
        except ValidationError as e:
            print(f"\n  ✗ {e}")
            _pause()
            return
        print(f"\n  ✓ Record #{record_id} restored.")
    _pause()


def purge_voided() -> None:
    print("\n═══ Purge Voided Records ═══")
    print("\n  Hard-deletes voided rows older than a cut-off, for")
    print("  retention. The amendment trail keeps a note that each one")
    print("  existed. This cannot be undone.")
    before = _input("Delete voided rows dated before (YYYY-MM-DD)",
                    allow_empty=False)
    try:
        preview = audit.purge_voided(before_date=before, dry_run=True)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  {preview.purged} row(s) would be deleted.")
    if not preview.purged:
        _pause()
        return
    if _input("Type 'PURGE' to confirm") != "PURGE":
        print("  Cancelled.")
        return
    result = audit.purge_voided(before_date=before,
                               actor=_input("Your username", default="cli"))
    print(f"\n  ✓ Purged {result.purged} row(s).")
    _pause()


# ── Amendment trail ─────────────────────────────────────────────────

def amendment_trail() -> None:
    print("\n═══ Amendment Trail ═══")
    scope = _pick_from("Show amendments for",
                       ["One record", "One student", "Everything"],
                       default="Everything")
    kwargs: dict = {}
    if scope == "One record":
        kwargs["record_id"] = _pick_record_id()
    elif scope == "One student":
        kwargs["student_id"] = _input("Student ID", allow_empty=False)
    else:
        kwargs["date_from"], kwargs["date_to"] = _window()
        kwargs["limit"] = 60

    try:
        rows = audit.list_amendments(**kwargs)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not rows:
        print("\n  Nothing has been amended.")
        _pause()
        return

    print(f"\n  {len(rows)} amendment(s), newest first:\n")
    for entry in rows:
        print(f"    {entry.amended_at or '?':<20}{entry.action:<12}"
              f"{entry.student_id:<12}{entry.date:<12}")
        print(f"        {entry.summary}")
        if entry.reason:
            print(f"        reason: {entry.reason}")
    _pause()


def amendment_summary() -> None:
    print("\n═══ Amendment Summary ═══")
    date_from, date_to = _window()
    counts = audit.amendment_summary(date_from=date_from, date_to=date_to)
    total = sum(counts.values())
    if not total:
        print("\n  No amendments in that window.")
        _pause()
        return
    print(f"\n  {total} amendment(s) between {date_from} and {date_to}:\n")
    for action, count in counts.items():
        if count:
            print(f"    {action:<14}{count:>6}")
    worst = audit.most_amended(date_from=date_from, date_to=date_to, limit=5)
    if worst:
        print("\n  Most amended learners:")
        for student_id, count in worst:
            print(f"    {student_id:<14}{count:>6}")
        print("\n  A learner amended every week is either being mismarked")
        print("  or is a pastoral question. Both are worth following up.")
    _pause()


# ── Submenu dispatcher ─────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Mark Code Reference",        show_codes),
    ("Code Breakdown Report",      code_report),
    ("Recode a Record",            recode_record),
    ("Backfill Missing Codes",     backfill),
    ("List Absence Reasons",       list_reasons),
    ("Add Absence Reason",         add_reason),
    ("Archive Absence Reason",     archive_reason),
    ("Authorisation Queue",        authorisation_queue),
    ("Authorise an Absence",       authorise_absence),
    ("Authorise a Date Range",     authorise_window),
    ("Withdraw an Authorisation",  withdraw_authorisation),
    ("Authorisations by Staff",    who_authorises),
    ("Mark Off Site",              mark_offsite),
    ("Off-Site Register",          offsite_register),
    ("Void a Record",              void_record),
    ("Voided Records",             voided_records),
    ("Purge Voided Records",       purge_voided),
    ("Amendment Trail",            amendment_trail),
    ("Amendment Summary",          amendment_summary),
]


def run() -> None:
    while True:
        print("\n── Codes, Authorisation & Audit ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Attendance codes CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()
