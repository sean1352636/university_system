"""CLI flows for Sixth Form Exam Entries."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.assessment.exam_entries import exam_entries
from education_system.sixthform_system.modules.domain.students.students import students
from education_system.sixthform_system.modules.domain.assessment.exam_entries import exam_entries as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.academics.subjects import subjects as subjects_data
from education_system.sixthform_system.modules.domain.assessment.exam_entries.exam_entries import (
    DEFAULT_SEASON,
    DEFAULT_STATUS,
    ExamEntry,
    SEASONS,
    STATUSES,
    TIERS,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.students.students.students import A_LEVEL_SUBJECTS
from education_system.sixthform_system.modules.domain.academics.subjects.subjects import EXAM_BOARDS

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _active_subjects() -> list[str]:
    try:
        return subjects_data.get_active_names() or list(A_LEVEL_SUBJECTS)
    except Exception:
        logger.exception("Falling back to seed subject list")
        return list(A_LEVEL_SUBJECTS)


def _default_year() -> int:
    today = _date.today()
    return today.year if today.month < 9 else today.year + 1


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
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


def _pick_from(label: str, options: list[str], default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print(f"    Out of range (1..{len(options)}).")
            continue
        return options[n - 1]


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            print(f"    Out of range (1..{len(students)}).")
            continue
        match = next((s for s in students
                      if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── CRUD entry points ──────────────────────────────────────────────

def _print_entries(rows: list[ExamEntry]) -> None:
    if not rows:
        print("\n  (no entries)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Subject':<18}  {'Board':<10}  "
          f"{'Paper':<10}  {'Season':<8}  {'Year':>4}  "
          f"{'Cand. #':<10}  {'Status':<10}  Fee")
    print("  " + "-" * 110)
    for e in rows:
        fee = f"£{e.fee:.2f}" if e.fee is not None else "—"
        print(f"  {e.entry_id:>4}  {e.student_id:<10}  "
              f"{e.subject[:18]:<18}  {e.exam_board[:10]:<10}  "
              f"{e.paper_code[:10]:<10}  {e.season:<8}  {e.year:>4}  "
              f"{(e.candidate_no or '—'):<10}  {e.status:<10}  {fee}")
    print(f"\n  {len(rows)} entry/entries.")


def list_all() -> None:
    print("\n═══ Exam Entries ═══")
    try:
        rows = data.list_entries()
    except Exception as e:
        logger.exception("CLI list_entries failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_entries(rows)
    _row_action_loop(rows)


def filter_entries() -> None:
    print("\n═══ Filter Entries ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        subject = _input("Subject (exact)") or None
        if subject and subject not in _active_subjects():
            print(f"  ✗ Unknown subject: {subject}")
            _pause()
            return
        board = _input(f"Exam board ({'/'.join(EXAM_BOARDS)})") or None
        season = _input(f"Season ({'/'.join(SEASONS)})") or None
        year_raw = _input("Year (e.g. 2026)")
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        paper = _input("Paper code") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    year = None
    if year_raw:
        try:
            year = int(year_raw)
        except ValueError:
            print("  ✗ Year must be a number.")
            _pause()
            return
    try:
        rows = data.list_entries(
            student_id=sid, subject=subject, exam_board=board,
            season=season, year=year, status=status, paper_code=paper,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_entries(rows)
    _row_action_loop(rows)


def per_student() -> None:
    print("\n═══ Per-Student Entries ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    rows = data.entries_for_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_entries(rows)
    _row_action_loop(rows)


def _collect_entry(existing: ExamEntry | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    if is_edit:
        payload["student_id"] = existing.student_id
    else:
        payload["student_id"] = _pick_student()

    print("\n  ── Entry details ──")
    payload["subject"] = _pick_from(
        "Subject", _active_subjects(),
        default=(existing.subject if is_edit else _active_subjects()[0]))
    payload["exam_board"] = _pick_from(
        "Exam board", list(EXAM_BOARDS),
        default=(existing.exam_board if is_edit else EXAM_BOARDS[0]))
    payload["paper_code"] = _input(
        "Paper code (e.g. 9MA0/01)",
        default=(existing.paper_code if is_edit else ""),
        allow_empty=False)
    payload["paper_title"] = _input(
        "Paper title (optional)",
        default=(existing.paper_title or "") if is_edit else "")
    payload["season"] = _pick_from(
        "Season", list(SEASONS),
        default=(existing.season if is_edit else DEFAULT_SEASON))
    payload["year"] = _input(
        "Year",
        default=(str(existing.year) if is_edit else str(_default_year())),
        allow_empty=False)
    payload["candidate_no"] = _input(
        "Candidate number (optional)",
        default=(existing.candidate_no or "") if is_edit else "")
    payload["tier"] = _pick_from(
        "Tier (or 'None')",
        ["None", *TIERS],
        default=(existing.tier if (is_edit and existing.tier) else "None"))
    if payload["tier"] == "None":
        payload["tier"] = ""
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["fee"] = _input(
        "Fee in £ (optional)",
        default=(f"{existing.fee:.2f}"
                 if (is_edit and existing.fee is not None) else ""))
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_entry() -> None:
    print("\n═══ New Exam Entry ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_entry(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        e = data.create_entry(payload)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    except Exception as ex:
        logger.exception("CLI new_entry failed")
        print(f"\n  ✗ Unexpected error: {ex}")
        _pause()
        return
    print(f"\n  ✓ Created entry #{e.entry_id}")
    print(f"      {e.student_id} for {e.paper_code} ({e.season} {e.year})")
    _pause()


def edit_entry(entry_id: int | None = None) -> None:
    print("\n═══ Edit Entry ═══")
    try:
        eid = entry_id if entry_id is not None else int(
            _input("Entry ID", allow_empty=False))
    except ValueError:
        print("  ✗ Entry ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_entry(eid)
    if existing is None:
        print(f"  ✗ No entry #{eid}")
        _pause()
        return
    try:
        payload = _collect_entry(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_entry(eid, payload)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    except Exception as ex:
        logger.exception("CLI update_entry(%d) failed", eid)
        print(f"\n  ✗ Unexpected error: {ex}")
        _pause()
        return
    print(f"\n  ✓ Updated entry #{eid}")
    _pause()


def delete_entry_flow(entry_id: int | None = None) -> None:
    print("\n═══ Delete Entry ═══")
    try:
        eid = entry_id if entry_id is not None else int(
            _input("Entry ID", allow_empty=False))
    except ValueError:
        print("  ✗ Entry ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_entry(eid)
    if existing is None:
        print(f"  ✗ No entry #{eid}")
        _pause()
        return
    confirm = _input(
        f"Delete entry #{eid} "
        f"({existing.student_id} on {existing.paper_code}, "
        f"{existing.season} {existing.year})? Type 'yes' to confirm",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_entry(eid):
            print(f"\n  ✓ Deleted #{eid}")
    except Exception as ex:
        logger.exception("CLI delete_entry crashed")
        print(f"\n  ✗ Unexpected error: {ex}")
    _pause()


# ── Bulk sheet ────────────────────────────────────────────────────

def bulk_sheet() -> None:
    print("\n═══ Bulk Entry Sheet ═══")
    print("  Statuses: 1=Entered  2=Withdrawn  3=Absent  4=Sat  S=Skip")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        subject = _pick_from("Subject", _active_subjects())
        board = _pick_from("Exam board", list(EXAM_BOARDS))
        paper_code = _input("Paper code", allow_empty=False)
        paper_title = _input("Paper title (optional)") or None
        season = _pick_from("Season", list(SEASONS),
                             default=DEFAULT_SEASON)
        year_raw = _input("Year",
                          default=str(_default_year()),
                          allow_empty=False)
        try:
            year = int(year_raw)
        except ValueError:
            print("  ✗ Year must be a number.")
            _pause()
            return
        tier_raw = _pick_from("Tier (or 'None')",
                               ["None", *TIERS], default="None")
        tier = None if tier_raw == "None" else tier_raw
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        view = data.bulk_view(subject, paper_code, season, year)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if not view:
        print(f"  ✗ No students take {subject}.")
        _pause()
        return

    status_map = {"1": "Entered", "2": "Withdrawn", "3": "Absent", "4": "Sat"}
    print(f"\n  {paper_code}  ·  {subject}  ·  {season} {year}  ·  "
          f"{len(view)} candidate(s)")

    payload: dict[str, dict[str, Any]] = {}
    for v in view:
        existing = ""
        if v.entry:
            existing = (f"  [current: cand={v.entry.candidate_no or '—'}, "
                        f"{v.entry.status}]")
        print(f"\n  {v.student_id}  {v.full_name}{existing}")
        try:
            raw = _input(
                "  Status (1-4 / S)",
                default=(v.entry.status if v.entry else DEFAULT_STATUS))
        except _UserAbort:
            print("\n  Cancelled.")
            return
        if raw.lower() == "s":
            continue
        status = status_map.get(raw, raw)
        if status not in STATUSES:
            print(f"    ✗ Unknown status {raw!r}, skipping.")
            continue
        try:
            cand = _input(
                "  Candidate # (optional)",
                default=(v.entry.candidate_no or "") if v.entry else "")
            fee = _input(
                "  Fee in £ (optional)",
                default=(f"{v.entry.fee:.2f}"
                         if (v.entry and v.entry.fee is not None) else ""))
            notes = _input(
                "  Notes (optional)",
                default=(v.entry.notes or "") if v.entry else "")
        except _UserAbort:
            print("\n  Cancelled.")
            return
        payload[v.student_id] = {
            "candidate_no": cand, "status": status,
            "fee": fee, "notes": notes,
        }

    if not payload:
        print("\n  (nothing changed)")
        _pause()
        return
    try:
        n = data.save_bulk(
            subject=subject, exam_board=board, paper_code=paper_code,
            paper_title=paper_title, season=season, year=year, tier=tier,
            entries=payload,
        )
        print(f"\n  ✓ Saved {n} entry/entries.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("save_bulk crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Series summary ────────────────────────────────────────────────

def series_summary() -> None:
    print("\n═══ Series Summary ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        board = _input(f"Board ({'/'.join(EXAM_BOARDS)})") or None
        season = _input(f"Season ({'/'.join(SEASONS)})") or None
        year_raw = _input("Year")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    year = None
    if year_raw:
        try:
            year = int(year_raw)
        except ValueError:
            print("  ✗ Year must be a number.")
            _pause()
            return
    try:
        summ = data.series_summary(
            exam_board=board, season=season, year=year)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return

    print(f"\n  Total entries: {summ.total}")
    if summ.total == 0:
        _pause()
        return
    print("\n  By status:")
    for st in STATUSES:
        n = summ.by_status.get(st, 0)
        print(f"    {st:<12} : {n}")
    print("\n  By subject:")
    for subj, n in sorted(summ.by_subject.items()):
        print(f"    {subj:<22} : {n}")
    print(f"\n  Total fees recorded: £{summ.total_fee:.2f}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[ExamEntry]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  E) Edit   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("e", "d"):
            print("    Pick E, D, or Enter.")
            continue
        try:
            raw = _input("Entry ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            eid = int(raw)
        except ValueError:
            print("    Entry ID must be a whole number.")
            continue
        if choice == "e":
            edit_entry(eid)
        elif choice == "d":
            delete_entry_flow(eid)
        return


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Entries",        list_all),
    ("Filter Entries",      filter_entries),
    ("Per-Student Entries", per_student),
    ("New Entry",           new_entry),
    ("Bulk Entry Sheet",    bulk_sheet),
    ("Series Summary",      series_summary),
    ("Edit Entry",          edit_entry),
    ("Delete Entry",        delete_entry_flow),
]


def run() -> None:
    while True:
        print("\n── Exam Entries ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
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
            logger.exception("Exam-entries CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Exam Entries":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Exam-entries CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
