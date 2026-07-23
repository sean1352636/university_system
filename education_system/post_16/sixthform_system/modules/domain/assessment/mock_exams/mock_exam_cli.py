"""CLI flows for Sixth Form Mock Exams."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.assessment.mock_exams import mock_exams
from education_system.post_16.sixthform_system.modules.domain.students.students import students
from education_system.post_16.sixthform_system.modules.domain.assessment.mock_exams import mock_exams as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.academics.subjects import subjects as subjects_data
from education_system.post_16.sixthform_system.modules.domain.assessment.gradebook.gradebook import LETTER_GRADES, pct_to_letter
from education_system.post_16.sixthform_system.modules.domain.assessment.mock_exams.mock_exams import (
    MockExam,
    StudentMockSummary,
    ValidationError,
    derived_pct,
)
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


def _pick_mock() -> int:
    mocks = data.list_mocks()
    if not mocks:
        print("    No mocks exist.")
        raise _UserAbort
    print("\n  Mocks:")
    for i, m in enumerate(mocks, 1):
        print(f"    {i:>3}) #{m.mock_id:<3}  {m.title[:30]:<30}  "
              f"({m.subject}, {m.date_sat}, max {m.max_marks})")
    while True:
        raw = _input(f"  Pick #1..{len(mocks)} (or mock ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(mocks):
                return mocks[n - 1].mock_id
            target = next((m for m in mocks if m.mock_id == n), None)
            if target:
                return target.mock_id
            print(f"    Out of range (1..{len(mocks)}).")


# ── Mock form ──────────────────────────────────────────────────────

def _today() -> str:
    return _date.today().isoformat()


def _collect_mock(existing: MockExam | None) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    print("\n  ── Mock paper details ──")
    payload["title"] = _input(
        "Title", default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["subject"] = _pick_from(
        "Subject", _active_subjects(),
        default=(existing.subject if is_edit else _active_subjects()[0]))
    payload["exam_board"] = _pick_from(
        "Exam board (or 'None')",
        ["None", *EXAM_BOARDS],
        default=(existing.exam_board if (is_edit and existing.exam_board)
                 else "None"))
    if payload["exam_board"] == "None":
        payload["exam_board"] = ""
    payload["paper_number"] = _input(
        "Paper number (optional)",
        default=(str(existing.paper_number)
                 if (is_edit and existing.paper_number is not None) else ""))
    payload["date_sat"] = _input(
        "Date sat (YYYY-MM-DD)",
        default=(existing.date_sat if is_edit else _today()),
        allow_empty=False)
    payload["duration_minutes"] = _input(
        "Duration (minutes, optional)",
        default=(str(existing.duration_minutes)
                 if (is_edit and existing.duration_minutes is not None) else ""))
    payload["max_marks"] = _input(
        "Max marks",
        default=(str(existing.max_marks) if is_edit else "100"),
        allow_empty=False)
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return payload


# ── CRUD entry points ──────────────────────────────────────────────

def _print_mocks(rows: list[MockExam]) -> None:
    if not rows:
        print("\n  (no mocks)")
        return
    print()
    print(f"  {'#':>4}  {'Title':<32}  {'Subject':<18}  {'Board':<10}  "
          f"{'P':>2}  {'Date':<10}  Max")
    print("  " + "-" * 90)
    for m in rows:
        print(f"  {m.mock_id:>4}  {m.title[:32]:<32}  {m.subject[:18]:<18}  "
              f"{(m.exam_board or '—')[:10]:<10}  "
              f"{(str(m.paper_number) if m.paper_number is not None else '—'):>2}  "
              f"{m.date_sat:<10}  {m.max_marks}")
    print(f"\n  {len(rows)} mock(s).")


def list_all() -> None:
    print("\n═══ Mock Exams ═══")
    try:
        rows = data.list_mocks()
    except Exception as e:
        logger.exception("CLI list_mocks failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_mocks(rows)
    _row_action_loop(rows)


def filter_mocks() -> None:
    print("\n═══ Filter Mocks ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        subject = _input("Subject (exact)") or None
        if subject and subject not in _active_subjects():
            print(f"  ✗ Unknown subject: {subject}")
            _pause()
            return
        board = _input("Exam board") or None
        if board and board not in EXAM_BOARDS:
            print(f"  ✗ Unknown exam board: {board}")
            _pause()
            return
        date_from = _input("From (YYYY-MM-DD)") or None
        date_to = _input("To (YYYY-MM-DD)") or None
        search = _input("Search (title / notes)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_mocks(
            subject=subject, exam_board=board,
            date_from=date_from, date_to=date_to, search=search)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_mocks(rows)
    _row_action_loop(rows)


def new_mock() -> None:
    print("\n═══ New Mock Exam ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_mock(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = data.create_mock(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI new_mock failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print()
    print(f"  ✓ Created mock #{m.mock_id}")
    print(f"      Title    : {m.title}")
    print(f"      Subject  : {m.subject}")
    print(f"      Date sat : {m.date_sat}")
    print(f"      Max marks: {m.max_marks}")
    _pause()


def view_mock(mock_id: int | None = None) -> None:
    print("\n═══ View Mock ═══")
    try:
        mid = mock_id if mock_id is not None else int(
            _input("Mock ID", allow_empty=False))
    except ValueError:
        print("  ✗ Mock ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    m = data.get_mock(mid)
    if m is None:
        print(f"  ✗ No mock #{mid}")
        _pause()
        return
    print()
    print(f"    Mock ID     : #{m.mock_id}")
    print(f"    Title       : {m.title}")
    print(f"    Subject     : {m.subject}")
    print(f"    Exam board  : {m.exam_board or '—'}")
    print(f"    Paper       : "
          f"{m.paper_number if m.paper_number is not None else '—'}")
    print(f"    Date sat    : {m.date_sat}")
    print(f"    Duration    : "
          f"{m.duration_minutes} mins" if m.duration_minutes else "    Duration    : —")
    print(f"    Max marks   : {m.max_marks}")
    if m.notes:
        print(f"    Notes       : {m.notes}")
    results = data.list_results(mock_id=mid)
    print(f"\n    Results recorded: {len(results)}")
    _pause()


def edit_mock(mock_id: int | None = None) -> None:
    print("\n═══ Edit Mock ═══")
    try:
        mid = mock_id if mock_id is not None else int(
            _input("Mock ID", allow_empty=False))
    except ValueError:
        print("  ✗ Mock ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_mock(mid)
    if existing is None:
        print(f"  ✗ No mock #{mid}")
        _pause()
        return
    try:
        payload = _collect_mock(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = data.update_mock(mid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_mock(%d) failed", mid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated mock #{m.mock_id}")
    _pause()


def delete_mock_flow(mock_id: int | None = None) -> None:
    print("\n═══ Delete Mock ═══")
    try:
        mid = mock_id if mock_id is not None else int(
            _input("Mock ID", allow_empty=False))
    except ValueError:
        print("  ✗ Mock ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_mock(mid)
    if existing is None:
        print(f"  ✗ No mock #{mid}")
        _pause()
        return
    n = len(data.list_results(mock_id=mid))
    extra = f" ({n} result row(s) will be removed)" if n else ""
    confirm = _input(
        f"Delete '{existing.title}'?{extra} Type 'yes' to confirm",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_mock(mid):
            print(f"\n  ✓ Deleted mock #{mid}")
    except Exception as e:
        logger.exception("CLI delete_mock crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Results sheet ──────────────────────────────────────────────────

def results_sheet() -> None:
    print("\n═══ Mock Results Sheet ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        mid = _pick_mock()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _results_sheet_for(mid)


def _results_sheet_for(mid: int) -> None:
    m = data.get_mock(mid)
    if m is None:
        print(f"  ✗ No mock #{mid}")
        _pause()
        return
    try:
        view = data.result_view(mid)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("result_view failed")
        print(f"  ✗ {e}")
        _pause()
        return
    if not view:
        print(f"  ✗ No students take {m.subject}.")
        _pause()
        return

    print(f"\n  {m.title}  ·  max {m.max_marks}")
    print("  Boundaries: A*≥90%  A≥80%  B≥70%  C≥60%  D≥50%  E≥40%")
    print("  Press Enter on marks to skip a student. Leave Grade override "
          "blank to use the auto-derived letter.")

    payload: dict[str, dict[str, Any]] = {}
    for v in view:
        existing = ""
        if v.result:
            existing = (f"  [current: marks="
                        f"{v.result.marks if v.result.marks is not None else '—'}"
                        + (f", grade={v.result.grade}" if v.result.grade else "")
                        + "]")
        print(f"\n  {v.student_id}  {v.full_name}{existing}")
        try:
            marks_raw = _input(
                "  Marks (blank = skip)",
                default=(str(v.result.marks)
                         if v.result and v.result.marks is not None else ""))
        except _UserAbort:
            print("\n  Cancelled.")
            return
        if not marks_raw:
            continue
        # Show derived letter as a hint before asking for an override.
        try:
            mk_int = int(marks_raw)
            pct = derived_pct(mk_int, m.max_marks)
            print(f"    → {pct}%  letter (auto): {pct_to_letter(pct)}")
        except ValueError:
            pass

        try:
            grade = _input(
                "  Grade override (blank = auto)",
                default=(v.result.grade or "") if v.result else "")
            notes = _input(
                "  Notes (optional)",
                default=(v.result.notes or "") if v.result else "")
        except _UserAbort:
            print("\n  Cancelled.")
            return
        payload[v.student_id] = {
            "marks": marks_raw,
            "grade": grade,
            "notes": notes,
        }

    if not payload:
        print("\n  (nothing changed)")
        _pause()
        return
    try:
        n = data.save_results(mid, payload)
        print(f"\n  ✓ Saved {n} result(s).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("save_results crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Summary ────────────────────────────────────────────────────────

def subject_summary() -> None:
    print("\n═══ Per-Subject Mock Summary ═══")
    try:
        subject = _pick_from("Subject", _active_subjects())
        date_from = _input("From (YYYY-MM-DD, optional)") or None
        date_to = _input("To (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        per = data.per_student_summary_for_subject(
            subject, date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return

    if not per:
        print(f"\n  (no mocks for {subject})")
        _pause()
        return
    students_index = {s.student_id: s for s in student_data.list_students()}
    print()
    print(f"  {'Student':<10}  {'Name':<24}  {'Sat':>3}  {'Total':>5}  "
          f"{'Avg %':>6}  {'Best':>4}  {'Worst':>5}")
    print("  " + "-" * 70)
    for sid, s in sorted(per.items()):
        student = students_index.get(sid)
        name = (student.full_name if student else "(deleted)")[:24]
        avg = f"{s.avg_pct}%" if s.avg_pct is not None else "—"
        print(f"  {sid:<10}  {name:<24}  {s.mocks_sat:>3}  "
              f"{s.mocks_total:>5}  {avg:>6}  "
              f"{(s.best_letter or '—'):>4}  "
              f"{(s.worst_letter or '—'):>5}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[MockExam]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   R) Results sheet   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "r", "d"):
            print("    Pick V, E, R, D, or Enter.")
            continue
        try:
            raw = _input("Mock ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            mid = int(raw)
        except ValueError:
            print("    Mock ID must be a whole number.")
            continue
        if choice == "v":
            view_mock(mid)
        elif choice == "e":
            edit_mock(mid)
        elif choice == "r":
            _results_sheet_for(mid)
        elif choice == "d":
            delete_mock_flow(mid)
        return


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Mocks",       list_all),
    ("Filter Mocks",     filter_mocks),
    ("New Mock",         new_mock),
    ("Results Sheet",    results_sheet),
    ("Subject Summary",  subject_summary),
    ("View Mock",        view_mock),
    ("Edit Mock",        edit_mock),
    ("Delete Mock",      delete_mock_flow),
]


def run() -> None:
    while True:
        print("\n── Mock Exams ──")
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
            logger.exception("Mock-exam CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Mock Exams":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Mock-exam CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
