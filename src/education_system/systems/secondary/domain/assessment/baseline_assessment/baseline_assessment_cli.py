"""CLI handlers for baseline assessment."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.baseline_assessment import (
    baseline_assessment as data,
)
from education_system.systems.secondary.domain.assessment.baseline_assessment.baseline_assessment import (
    TEST_TYPES,
)
from education_system.systems.secondary.domain.academics.subjects import (
    subjects as subjects_data,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_tests(rows: list[data.BaselineTest]) -> None:
    if not rows:
        print("  (no tests)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Yr':<3} {'Type':<8} "
          f"{'Subj':<6} {'Name':<32} {'Max':<5}")
    print(f"  {'-'*5} {'-'*10} {'-'*3} {'-'*8} {'-'*6} {'-'*32} {'-'*5}")
    for t in rows:
        print(f"  {t.test_id:<5} {t.test_date:<10} {t.year_group:<3} "
              f"{t.test_type[:8]:<8} "
              f"{(t.subject_code or '-'):<6} {t.name[:32]:<32} "
              f"{(t.max_marks if t.max_marks else '-'):<5}")


def _print_results(rows: list[data.BaselineResult]) -> None:
    if not rows:
        print("  (no results)")
        return
    print(f"  {'ID':<5} {'Pupil':<12} {'Yr':<3} {'Name':<20} "
          f"{'Marks':<10} {'%':<5} {'StdSc':<6} {'Grade':<5}")
    print(f"  {'-'*5} {'-'*12} {'-'*3} {'-'*20} {'-'*10} {'-'*5} "
          f"{'-'*6} {'-'*5}")
    for r in rows:
        marks = ("-" if r.marks_awarded is None
                 else (f"{r.marks_awarded:g}/{r.test_max:g}"
                        if r.test_max else f"{r.marks_awarded:g}"))
        pct = f"{r.mark_pct:.0f}" if r.mark_pct is not None else "-"
        ss = (f"{r.standardised_score:.0f}"
              if r.standardised_score is not None else "-")
        print(f"  {r.result_id:<5} {r.pupil_id:<12} "
              f"{(r.pupil_year or '-'):<3} "
              f"{(r.test_name or '-')[:20]:<20} {marks:<10} "
              f"{pct:<5} {ss:<6} {(r.baseline_grade or '-'):<5}")


@_safe
def open_baseline_assessment() -> None:
    logger.debug("CLI: open_baseline_assessment")
    while True:
        print("\n  ── Baseline Assessment ──")
        print("  Tests")
        print("    1) New test")
        print("    2) List tests")
        print("    3) Edit test")
        print("    4) Delete test")
        print("  Results")
        print("    5) Record / update result")
        print("    6) List results for a test")
        print("    7) Pupil results history")
        print("    8) Delete result")
        print("    9) Test summary stats")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_test, "2": _list_tests, "3": _edit_test,
            "4": _delete_test,
            "5": _upsert_result, "6": _list_results,
            "7": _pupil_results, "8": _delete_result,
            "9": _summary,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_test(existing: data.BaselineTest | None = None
                   ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    f["name"] = ask("Test name", existing.name if existing else None)
    if not existing:
        print("  Active subjects (optional):")
        for s in subjects_data.list_all(active_only=True)[:20]:
            print(f"    #{s.subject_id:<4} {s.code:<8} {s.name}")
    f["subject_id"] = ask("Subject ID (blank ok)",
                           existing.subject_id if existing else None)
    f["year_group"] = ask(f"Year ({'/'.join(YEAR_GROUPS)})",
                           existing.year_group if existing else None)
    f["test_type"]  = ask(f"Type ({'/'.join(TEST_TYPES)})",
                           existing.test_type if existing else "School")
    f["test_date"]  = ask("Date (YYYY-MM-DD, blank = today)",
                           existing.test_date if existing else None)
    f["max_marks"]  = ask("Max marks (blank ok)",
                           existing.max_marks if existing else None)
    f["notes"]      = ask("Notes",
                           existing.notes if existing else None)
    return f


@_safe
def _new_test() -> None:
    print("\n  ── New Baseline Test ──")
    fields = _collect_test()
    t = data.create_test(fields)
    print(f"  Created test #{t.test_id} {t.name} (Yr{t.year_group}, "
          f"{t.test_type})")


@_safe
def _list_tests() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ttype = _prompt(f"  Type ({'/'.join(TEST_TYPES)}, blank): ") or None
    rows = data.list_tests(year_group=yg, test_type=ttype)
    print(f"\n  {len(rows)} test(s):")
    _print_tests(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id(label: str) -> int | None:
    raw = _prompt(f"  {label}: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"  {label} must be a number.")
        return None


@_safe
def _edit_test() -> None:
    tid = _ask_id("Test ID")
    if tid is None:
        return
    existing = data.get_test(tid)
    if existing is None:
        print("  No test with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_test(existing)
    t = data.update_test(tid, fields)
    print(f"  Updated test #{t.test_id}")


@_safe
def _delete_test() -> None:
    tid = _ask_id("Test ID")
    if tid is None:
        return
    t = data.get_test(tid)
    if t is None:
        print("  No test with that ID.")
        return
    confirm = _prompt(
        f"  Delete test '{t.name}' and ALL its results? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_test(tid)
    print(f"  Deleted test #{tid}.")


@_safe
def _upsert_result() -> None:
    tid = _ask_id("Test ID")
    if tid is None:
        return
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    marks = _prompt("  Marks awarded (blank ok): ") or None
    ss = _prompt("  Standardised score (40-160, blank ok): ") or None
    grade = _prompt("  Baseline grade (blank ok): ") or None
    notes = _prompt("  Notes (blank ok): ") or None
    r = data.upsert_result(tid, {
        "pupil_id": pid, "marks_awarded": marks,
        "standardised_score": ss, "baseline_grade": grade,
        "notes": notes,
    })
    print(f"  Saved result #{r.result_id}: {r.pupil_id} marks="
          f"{r.marks_awarded} pct={r.mark_pct} ss={r.standardised_score} "
          f"grade={r.baseline_grade or '-'}")


@_safe
def _list_results() -> None:
    tid = _ask_id("Test ID")
    if tid is None:
        return
    t = data.get_test(tid)
    if t is None:
        print("  No test with that ID.")
        return
    rows = data.list_results(tid)
    print(f"\n  {len(rows)} result(s) for '{t.name}':")
    _print_results(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_results() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rows = data.results_for_pupil(pid)
    print(f"\n  {len(rows)} baseline result(s) for {pid}:")
    _print_results(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_result() -> None:
    rid = _ask_id("Result ID")
    if rid is None:
        return
    r = data.get_result(rid)
    if r is None:
        print("  No result with that ID.")
        return
    confirm = _prompt(
        f"  Delete result #{rid} ({r.pupil_id} / {r.test_name})? "
        f"(y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_result(rid)
    print(f"  Deleted result #{rid}.")


@_safe
def _summary() -> None:
    tid = _ask_id("Test ID")
    if tid is None:
        return
    s = data.test_summary(tid)
    t = s["test"]
    print(f"\n  ── Summary: {t.name} (Yr{t.year_group}, "
          f"{t.test_date}) ──")
    print(f"  Results: {s['count']}    "
          f"Avg %: {s['avg_pct'] if s['avg_pct'] is not None else '-'}    "
          f"Min %: {s['min_pct'] if s['min_pct'] is not None else '-'}    "
          f"Max %: {s['max_pct'] if s['max_pct'] is not None else '-'}")
    if s["avg_standardised"] is not None:
        print(f"  Avg standardised score: {s['avg_standardised']}")
    if s["grades"]:
        print("  Grades: "
              + "   ".join(f"{k}: {v}"
                            for k, v in sorted(s["grades"].items())))
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Baseline Assessment": open_baseline_assessment}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching baseline_assessment CLI label: %s", label)
    handler()
    return True
