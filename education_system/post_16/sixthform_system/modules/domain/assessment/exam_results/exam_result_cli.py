"""CLI flows for Sixth Form Results Day."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.assessment.exam_entries import exam_entries
from education_system.post_16.sixthform_system.modules.domain.assessment.exam_results import exam_results
from education_system.post_16.sixthform_system.modules.domain.students.students import students
from education_system.post_16.sixthform_system.modules.domain.academics.subjects import subjects as entries_data
from education_system.post_16.sixthform_system.modules.domain.assessment.exam_results import exam_results as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.academics.subjects import subjects as subjects_data
from education_system.post_16.sixthform_system.modules.domain.assessment.exam_entries.exam_entries import SEASONS
from education_system.post_16.sixthform_system.modules.domain.assessment.exam_results.exam_results import (
    ResultRow,
    StudentResultsSummary,
    ValidationError,
)
from education_system.post_16.sixthform_system.modules.domain.assessment.gradebook.gradebook import LETTER_GRADES
from education_system.post_16.sixthform_system.modules.domain.students.students.students import A_LEVEL_SUBJECTS
from education_system.post_16.sixthform_system.modules.domain.academics.subjects.subjects import EXAM_BOARDS

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


def _pick_entry() -> int:
    entries = entries_data.list_entries()
    if not entries:
        print("    No exam entries exist.")
        raise _UserAbort
    print("\n  Exam entries:")
    for i, e in enumerate(entries, 1):
        print(f"    {i:>3}) #{e.entry_id:<3}  {e.student_id:<10}  "
              f"{e.paper_code:<10}  {e.season} {e.year}  ({e.status})")
    while True:
        raw = _input(f"  Pick #1..{len(entries)} (or entry ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(entries):
                return entries[n - 1].entry_id
            target = next((e for e in entries if e.entry_id == n), None)
            if target:
                return target.entry_id
            print(f"    Out of range (1..{len(entries)}).")


# ── Print helpers ──────────────────────────────────────────────────

def _print_results(rows: list[ResultRow]) -> None:
    if not rows:
        print("\n  (no results)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Subject':<18}  {'Paper':<10}  "
          f"{'Series':<14}  {'Grade':<5}  {'Marks':>5}  {'UMS':>4}  Released")
    print("  " + "-" * 100)
    for r in rows:
        series = f"{r.season} {r.year}"
        marks = (str(r.result.marks) if r.result.marks is not None else "—")
        ums = (str(r.result.ums) if r.result.ums is not None else "—")
        print(f"  {r.result.result_id:>4}  {r.student_id:<10}  "
              f"{r.subject[:18]:<18}  {r.paper_code[:10]:<10}  "
              f"{series:<14}  {r.result.grade:<5}  {marks:>5}  {ums:>4}  "
              f"{r.result.released_at or '—'}")
    print(f"\n  {len(rows)} result(s).")


# ── CRUD entry points ──────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ Results ═══")
    try:
        rows = data.list_results()
    except Exception as e:
        logger.exception("CLI list_results failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_results(rows)
    _row_action_loop(rows)


def filter_results() -> None:
    print("\n═══ Filter Results ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        subject = _input("Subject (exact)") or None
        if subject and subject not in _active_subjects():
            print(f"  ✗ Unknown subject: {subject}")
            _pause()
            return
        board = _input(f"Board ({'/'.join(EXAM_BOARDS)})") or None
        season = _input(f"Season ({'/'.join(SEASONS)})") or None
        year_raw = _input("Year")
        paper = _input("Paper code") or None
        grade = _input(f"Grade ({'/'.join(LETTER_GRADES)})") or None
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
        rows = data.list_results(
            student_id=sid, subject=subject, exam_board=board,
            season=season, year=year, paper_code=paper, grade=grade,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_results(rows)
    _row_action_loop(rows)


def new_result() -> None:
    print("\n═══ New Result ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        eid = _pick_entry()
        grade = _pick_from("Grade", list(LETTER_GRADES))
        marks = _input("Marks (optional)")
        ums = _input("UMS (optional)")
        released = _input("Released at (YYYY-MM-DD, optional)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.save_result({
            "entry_id":   eid,
            "grade":      grade,
            "marks":      marks,
            "ums":        ums,
            "released_at": released,
            "notes":      notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI new_result failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Saved result #{r.result_id} (entry {r.entry_id}: {r.grade})")
    _pause()


def edit_result(result_id: int | None = None) -> None:
    print("\n═══ Edit Result ═══")
    try:
        rid = result_id if result_id is not None else int(
            _input("Result ID", allow_empty=False))
    except ValueError:
        print("  ✗ Result ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_result(rid)
    if existing is None:
        print(f"  ✗ No result #{rid}")
        _pause()
        return
    entry = entries_data.get_entry(existing.entry_id)
    print(f"\n  Entry #{existing.entry_id}  "
          + (f"({entry.student_id} on {entry.paper_code}, "
             f"{entry.season} {entry.year})" if entry else "(deleted)"))
    try:
        grade = _pick_from("Grade", list(LETTER_GRADES),
                           default=existing.grade)
        marks = _input("Marks",
                       default=(str(existing.marks)
                                if existing.marks is not None else ""))
        ums = _input("UMS",
                     default=(str(existing.ums)
                              if existing.ums is not None else ""))
        released = _input("Released at", default=existing.released_at or "")
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_result(rid, {
            "grade": grade, "marks": marks, "ums": ums,
            "released_at": released, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_result crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated result #{rid}")
    _pause()


def delete_result_flow(result_id: int | None = None) -> None:
    print("\n═══ Delete Result ═══")
    try:
        rid = result_id if result_id is not None else int(
            _input("Result ID", allow_empty=False))
    except ValueError:
        print("  ✗ Result ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_result(rid)
    if existing is None:
        print(f"  ✗ No result #{rid}")
        _pause()
        return
    confirm = _input(
        f"Delete result #{rid} (entry {existing.entry_id})? "
        f"Type 'yes' to confirm",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_result(rid):
            print(f"\n  ✓ Deleted #{rid}")
    except Exception as e:
        logger.exception("CLI delete_result crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Bulk sheet ────────────────────────────────────────────────────

def bulk_sheet() -> None:
    print("\n═══ Bulk Results Sheet ═══")
    print("  Grades: 1=A*  2=A  3=B  4=C  5=D  6=E  7=U  S=Skip")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        paper = _input("Paper code", allow_empty=False)
        season = _pick_from("Season", list(SEASONS), default=SEASONS[0])
        year_raw = _input("Year", default=str(_default_year()),
                          allow_empty=False)
        released = _input("Released at (YYYY-MM-DD, optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        year = int(year_raw)
    except ValueError:
        print("  ✗ Year must be a number.")
        _pause()
        return
    try:
        view = data.bulk_view(paper, season, year)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if not view:
        print(f"  ✗ No entries found for {paper.upper()} ({season} {year}).")
        _pause()
        return

    grade_map = {"1": "A*", "2": "A", "3": "B", "4": "C",
                 "5": "D", "6": "E", "7": "U"}
    print(f"\n  {paper.upper()}  ·  {season} {year}  ·  "
          f"{len(view)} candidate(s)")
    payload: dict[int, dict[str, Any]] = {}
    for v in view:
        existing = ""
        if v.result:
            existing = (f"  [current: {v.result.grade}"
                        + (f" marks={v.result.marks}"
                           if v.result.marks is not None else "")
                        + "]")
        marker = " (Withdrawn)" if v.status == "Withdrawn" else ""
        print(f"\n  entry #{v.entry_id}  {v.student_id}  "
              f"{v.full_name}{marker}{existing}")
        try:
            default = (v.result.grade if v.result else "")
            raw = _input("  Grade (1-7 / S)", default=default)
        except _UserAbort:
            print("\n  Cancelled.")
            return
        if raw.lower() == "s":
            continue
        grade = grade_map.get(raw, raw)
        if grade not in LETTER_GRADES:
            print(f"    ✗ Unknown grade {raw!r}, skipping.")
            continue
        try:
            marks = _input(
                "  Marks (optional)",
                default=(str(v.result.marks)
                         if v.result and v.result.marks is not None else ""))
            ums = _input(
                "  UMS (optional)",
                default=(str(v.result.ums)
                         if v.result and v.result.ums is not None else ""))
            notes = _input(
                "  Notes (optional)",
                default=((v.result.notes or "") if v.result else ""))
        except _UserAbort:
            print("\n  Cancelled.")
            return
        payload[v.entry_id] = {
            "grade": grade, "marks": marks, "ums": ums, "notes": notes,
        }

    if not payload:
        print("\n  (nothing changed)")
        _pause()
        return
    try:
        n = data.save_bulk(
            paper_code=paper, season=season, year=year,
            released_at=released or None,
            entries=payload,
        )
        print(f"\n  ✓ Saved {n} result(s).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("save_bulk crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Per-student summary ───────────────────────────────────────────

def student_summary() -> None:
    print("\n═══ Per-Student Results ═══")
    try:
        sid = _input("Student ID", allow_empty=False)
        year_raw = _input("Year (optional)")
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
    student = student_data.get_student(sid)
    if student is None:
        print(f"  ✗ No student with id {sid}")
        _pause()
        return
    rows = data.results_for_student(sid, year=year)
    summ = data.per_student_summary(sid, year=year)
    print(f"\n  {student.student_id}  {student.full_name}")
    if not rows:
        print("  (no results)")
        _pause()
        return
    _print_results(rows)
    parts = [f"{g}={summ.by_grade.get(g, 0)}"
             for g in LETTER_GRADES if summ.by_grade.get(g)]
    print(f"  Total: {summ.total}  ·  Best: {summ.best or '—'}  ·  "
          f"Worst: {summ.worst or '—'}"
          + (f"  ·  {' '.join(parts)}" if parts else ""))
    _pause()


# ── Grade distribution ───────────────────────────────────────────

def distribution() -> None:
    print("\n═══ Grade Distribution ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        subject = _input("Subject (exact)") or None
        if subject and subject not in _active_subjects():
            print(f"  ✗ Unknown subject: {subject}")
            _pause()
            return
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
        dist = data.grade_distribution(
            subject=subject, exam_board=board, season=season, year=year)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return

    print(f"\n  Total results: {dist.total}")
    if not dist.total:
        _pause()
        return

    # ascii bar chart
    max_count = max(dist.counts.get(g, 0) for g in LETTER_GRADES)
    print()
    for g in LETTER_GRADES:
        n = dist.counts.get(g, 0)
        pct = round(100.0 * n / dist.total, 1)
        bar = "█" * (int((n / max_count) * 40) if max_count else 0)
        print(f"  {g:<2}  {bar:<40} {n:>4} ({pct}%)")
    print(f"\n  Pass (A*-E): {dist.pass_count}  ·  "
          f"Pass rate: {dist.pass_rate}%  ·  A*-A: {dist.top_rate}%")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[ResultRow]) -> None:
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
            raw = _input("Result ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            rid = int(raw)
        except ValueError:
            print("    Result ID must be a whole number.")
            continue
        if choice == "e":
            edit_result(rid)
        elif choice == "d":
            delete_result_flow(rid)
        return


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Results",      list_all),
    ("Filter Results",    filter_results),
    ("New Result",        new_result),
    ("Bulk Results Sheet", bulk_sheet),
    ("Per-Student",       student_summary),
    ("Grade Distribution", distribution),
    ("Edit Result",       edit_result),
    ("Delete Result",     delete_result_flow),
]


def run() -> None:
    while True:
        print("\n── Results Day ──")
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
            logger.exception("Results-day CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Results Day":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Results-day CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
