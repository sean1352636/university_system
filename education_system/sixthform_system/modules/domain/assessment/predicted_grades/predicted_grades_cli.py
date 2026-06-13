"""CLI flows for Sixth Form Predicted Grades.

Submenu: list / filter / per-student / new-or-update / group sheet /
edit / delete.
"""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups
from education_system.sixthform_system.modules.domain.academics.courses import courses
from education_system.sixthform_system.modules.domain.assessment.predicted_grades import predicted_grades
from education_system.sixthform_system.modules.domain.students.students import students
from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups as cg_data
from education_system.sixthform_system.modules.domain.academics.courses import courses as course_data
from education_system.sixthform_system.modules.domain.assessment.predicted_grades import predicted_grades as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.academics.subjects import subjects as subjects_data
from education_system.sixthform_system.modules.domain.assessment.gradebook.gradebook import LETTER_GRADES
from education_system.sixthform_system.modules.domain.assessment.predicted_grades.predicted_grades import (
    CONFIDENCE_LEVELS,
    DEFAULT_CONFIDENCE,
    Prediction,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.students.students.students import A_LEVEL_SUBJECTS

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


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students. Add one first.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or type a student ID)",
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
        print(f"    No matching student.")


def _pick_group() -> int:
    groups = cg_data.list_groups()
    if not groups:
        print("    No class groups exist.")
        raise _UserAbort
    courses = {c.course_id: c for c in course_data.list_courses()}
    print("\n  Class groups:")
    for i, g in enumerate(groups, 1):
        c = courses.get(g.course_id)
        code = c.course_code if c else f"#{g.course_id}"
        print(f"    {i:>3}) #{g.group_id:<3}  {code:<14}  {g.group_name}")
    while True:
        raw = _input(f"  Pick #1..{len(groups)} (or group ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(groups):
                return groups[n - 1].group_id
            target = next((g for g in groups if g.group_id == n), None)
            if target:
                return target.group_id
            print(f"    Out of range (1..{len(groups)}).")


# ── CRUD entry points ──────────────────────────────────────────────

def _print_predictions(rows: list[Prediction]) -> None:
    if not rows:
        print("\n  (no predictions)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Subject':<22}  "
          f"{'Grade':<5}  {'Confidence':<10}  By")
    print("  " + "-" * 78)
    for p in rows:
        print(f"  {p.prediction_id:>4}  {p.student_id:<10}  "
              f"{p.subject[:22]:<22}  {p.grade:<5}  "
              f"{p.confidence:<10}  {(p.predicted_by or '—')[:20]}")
    print(f"\n  {len(rows)} prediction(s).")


def list_all() -> None:
    print("\n═══ Predicted Grades ═══")
    try:
        rows = data.list_predictions()
    except Exception as e:
        logger.exception("CLI list_predictions failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_predictions(rows)
    _row_action_loop(rows)


def filter_predictions() -> None:
    print("\n═══ Filter Predictions ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        subj = _input("Subject (exact)") or None
        grade = _input(f"Grade ({'/'.join(LETTER_GRADES)})") or None
        confidence = _input(f"Confidence ({'/'.join(CONFIDENCE_LEVELS)})") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_predictions(
            student_id=sid, subject=subj,
            grade=grade, confidence=confidence,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI filter_predictions failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_predictions(rows)
    _row_action_loop(rows)


def per_student() -> None:
    print("\n═══ Per-Student Predictions ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    rows = data.predictions_for_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    if not rows:
        print("  (no predictions yet)")
        _pause()
        return
    print()
    print(f"  {'#':>4}  {'Subject':<22}  {'Grade':<5}  "
          f"{'Confidence':<10}  By")
    print("  " + "-" * 70)
    for p in rows:
        print(f"  {p.prediction_id:>4}  {p.subject[:22]:<22}  "
              f"{p.grade:<5}  {p.confidence:<10}  "
              f"{(p.predicted_by or '—')[:20]}")
    _pause()


def new_or_update() -> None:
    print("\n═══ New / Update Prediction ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        sid = _pick_student()
        subj = _pick_from("Subject", _active_subjects())
        grade = _pick_from("Grade", list(LETTER_GRADES))
        confidence = _pick_from("Confidence", list(CONFIDENCE_LEVELS),
                                 default=DEFAULT_CONFIDENCE)
        by = _input("Predicted by (optional)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.save_prediction({
            "student_id": sid, "subject": subj, "grade": grade,
            "confidence": confidence, "predicted_by": by, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("save_prediction crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Saved prediction #{p.prediction_id} "
          f"({p.student_id} in {p.subject}: {p.grade} / {p.confidence})")
    _pause()


def edit_prediction(prediction_id: int | None = None) -> None:
    print("\n═══ Edit Prediction ═══")
    try:
        pid = prediction_id if prediction_id is not None else int(
            _input("Prediction ID", allow_empty=False))
    except ValueError:
        print("  ✗ Prediction ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_prediction(pid)
    if existing is None:
        print(f"  ✗ No prediction #{pid}")
        _pause()
        return
    print(f"\n  {existing.student_id} · {existing.subject}")
    print(f"  Current: grade={existing.grade}, "
          f"confidence={existing.confidence}, "
          f"by={existing.predicted_by or '—'}")
    try:
        grade = _pick_from("Grade", list(LETTER_GRADES),
                           default=existing.grade)
        confidence = _pick_from("Confidence", list(CONFIDENCE_LEVELS),
                                 default=existing.confidence)
        by = _input("Predicted by", default=existing.predicted_by or "")
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_prediction(pid, {
            "grade": grade, "confidence": confidence,
            "predicted_by": by, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_prediction crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated prediction #{pid}")
    _pause()


def delete_prediction_flow(prediction_id: int | None = None) -> None:
    print("\n═══ Delete Prediction ═══")
    try:
        pid = prediction_id if prediction_id is not None else int(
            _input("Prediction ID", allow_empty=False))
    except ValueError:
        print("  ✗ Prediction ID must be a number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_prediction(pid)
    if existing is None:
        print(f"  ✗ No prediction #{pid}")
        _pause()
        return
    confirm = _input(
        f"Delete prediction #{pid} ({existing.student_id} / {existing.subject})? "
        f"Type 'yes'",
        default="no",
    )
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_prediction(pid):
            print(f"\n  ✓ Deleted #{pid}")
    except Exception as e:
        logger.exception("delete_prediction crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Group sheet ───────────────────────────────────────────────────

def group_sheet() -> None:
    print("\n═══ Group Prediction Sheet ═══")
    print("  Grades: 1=A*  2=A  3=B  4=C  5=D  6=E  7=U  S=Skip")
    print("  (type 'cancel' at any prompt to abort)\n")
    try:
        gid = _pick_group()
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        subject, view = data.group_prediction_view(gid)
    except Exception as e:
        logger.exception("group_prediction_view failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    if subject is None:
        print("  ✗ Group has no parent course/subject.")
        _pause()
        return
    if not view:
        print("  ✗ Group has no members.")
        _pause()
        return

    by = _input("Predicted by (optional)")
    grade_map = {
        "1": "A*", "2": "A", "3": "B", "4": "C", "5": "D", "6": "E", "7": "U",
    }

    print(f"\n  Subject: {subject}")
    payload: dict[str, dict[str, Any]] = {}
    for v in view:
        existing = (f"  [current: {v.prediction.grade} / "
                    f"{v.prediction.confidence}]"
                    if v.prediction else "")
        print(f"\n  {v.student_id}  {v.full_name}{existing}")
        try:
            default = (v.prediction.grade if v.prediction else "")
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
            confidence = _pick_from(
                "  Confidence", list(CONFIDENCE_LEVELS),
                default=(v.prediction.confidence if v.prediction else DEFAULT_CONFIDENCE))
            notes = _input(
                "  Notes (optional)",
                default=((v.prediction.notes or "") if v.prediction else ""))
        except _UserAbort:
            print("\n  Cancelled.")
            return
        payload[v.student_id] = {
            "grade": grade, "confidence": confidence,
            "notes": notes, "predicted_by": by,
        }

    if not payload:
        print("\n  (nothing changed)")
        _pause()
        return
    try:
        n = data.save_group_predictions(gid, payload)
        print(f"\n  ✓ Saved {n} prediction(s) for group #{gid} ({subject}).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except Exception as e:
        logger.exception("save_group_predictions crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[Prediction]) -> None:
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
            raw = _input("Prediction ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            pid = int(raw)
        except ValueError:
            print("    Prediction ID must be a whole number.")
            continue
        if choice == "e":
            edit_prediction(pid)
        elif choice == "d":
            delete_prediction_flow(pid)
        return


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Predictions",      list_all),
    ("Filter Predictions",    filter_predictions),
    ("Per-Student",           per_student),
    ("New / Update",          new_or_update),
    ("Group Prediction Sheet", group_sheet),
    ("Edit Prediction",       edit_prediction),
    ("Delete Prediction",     delete_prediction_flow),
]


def run() -> None:
    while True:
        print("\n── Predicted Grades ──")
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
            logger.exception("Predicted-grades CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Predicted Grades":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Predicted-grades CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
