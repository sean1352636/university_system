"""Prompt helpers, pickers and result printers shared by the bulk operation CLI flows.

Split out of ``bulk_operations_cli.py``, which re-exports every name here.
"""

from __future__ import annotations

from education_system.systems.sixth_form.domain.learners.bulk_operations.base import BulkResult
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import Job
from education_system.systems.sixth_form.domain.learners.students import students as student_data


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


def _pick_students() -> list[str]:
    """Multi-select student picker. Accepts comma-separated numeric
    picks or student-id tokens, or 'all' to take everyone."""
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    print("        (enter comma-separated numbers / IDs, "
          "or 'all')")
    while True:
        raw = _input("  Pick", allow_empty=False)
        if raw.lower() == "all":
            return [s.student_id for s in rows]
        tokens = [t.strip() for t in raw.replace(" ", ",").split(",")
                   if t.strip()]
        out: list[str] = []
        ok = True
        for t in tokens:
            if t.isdigit():
                n = int(t)
                if 1 <= n <= len(rows):
                    out.append(rows[n - 1].student_id)
                else:
                    print(f"    Out of range: {t}")
                    ok = False
                    break
            else:
                match = next((s for s in rows
                                if s.student_id.lower() == t.lower()), None)
                if match:
                    out.append(match.student_id)
                else:
                    print(f"    Unknown student: {t!r}")
                    ok = False
                    break
        if not ok:
            continue
        # De-dup, preserve order
        seen: set[str] = set()
        deduped = []
        for sid in out:
            if sid not in seen:
                deduped.append(sid)
                seen.add(sid)
        if not deduped:
            print("    No valid picks.")
            continue
        return deduped


# ── Result/Job printers ────────────────────────────────────────────

def _print_result(r: BulkResult, *, dry_run: bool = False) -> None:
    label = "Preview" if dry_run else "Result"
    print(f"\n  ── {label}: {r.operation} ──")
    print(f"    Targets   : {r.target_count}")
    print(f"    Successes : {r.success_count}")
    print(f"    Failures  : {r.failure_count}")
    if r.job_id:
        print(f"    Job id    : #{r.job_id}")
    # Show per-target diff/preview content if the op surfaced any.
    if r.success_ids:
        print("    Detail (first 20):")
        for tag in r.success_ids[:20]:
            print(f"      · {tag}")
        if len(r.success_ids) > 20:
            print(f"      ... +{len(r.success_ids) - 20} more.")
    elif dry_run and r.target_count and not r.failures:
        print(f"    Would touch {r.target_count} target(s).")
    if r.failures:
        print("    Failures:")
        for sid, reason in r.failures[:20]:
            print(f"      - {sid}: {reason}")
        if len(r.failures) > 20:
            print(f"      ... and {len(r.failures) - 20} more.")
    _pause()


def _print_jobs(rows: list[Job]) -> None:
    if not rows:
        print("\n  (no bulk jobs yet)")
        return
    print()
    print(f"  {'#':>5}  {'When':<19}  {'Operation':<18}  "
          f"{'Targets':>8}  {'OK':>5}  {'Fail':>5}  Summary")
    print("  " + "-" * 110)
    for j in rows:
        print(f"  {j.job_id:>5}  {j.ran_at[:19]:<19}  "
              f"{j.operation:<18}  {j.target_count:>8}  "
              f"{j.success_count:>5}  {j.failure_count:>5}  "
              f"{j.summary[:60]}")
    print(f"\n  {len(rows)} job(s).")


# ── Attendance bulk flows ──────────────────────────────────────────

def _pick_slot() -> int:
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    slots = _tt.list_slots()
    if not slots:
        print("    No timetable slots.")
        raise _UserAbort
    print("\n  Slots:")
    for i, s in enumerate(slots, 1):
        day = _tt.day_name(s.day)
        print(f"    {i:>3}) #{s.slot_id}  {day} P{s.period}  "
              f"group={s.group_id}  room={s.room or '—'}")
    while True:
        raw = _input("  Pick slot #", allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(slots):
                return slots[n - 1].slot_id
        print("    Out of range.")


def _pick_slots() -> list[int]:
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    slots = _tt.list_slots()
    if not slots:
        print("    No timetable slots.")
        raise _UserAbort
    print("\n  Slots:")
    for i, s in enumerate(slots, 1):
        day = _tt.day_name(s.day)
        print(f"    {i:>3}) #{s.slot_id}  {day} P{s.period}  "
              f"group={s.group_id}  room={s.room or '—'}")
    print("        (comma-separated numbers, or 'all')")
    while True:
        raw = _input("  Pick", allow_empty=False)
        if raw.lower() == "all":
            return [s.slot_id for s in slots]
        toks = [t.strip() for t in raw.replace(" ", ",").split(",") if t.strip()]
        out: list[int] = []
        ok = True
        for t in toks:
            if not t.isdigit():
                ok = False
                print(f"    Not a number: {t}")
                break
            n = int(t)
            if not (1 <= n <= len(slots)):
                ok = False
                print(f"    Out of range: {t}")
                break
            out.append(slots[n - 1].slot_id)
        if ok and out:
            return list(dict.fromkeys(out))


# ── Academic / pastoral bulk flows ─────────────────────────────────

def _pick_group() -> int | None:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    groups = _cg.list_groups()
    if not groups:
        print("    No class groups.")
        return None
    print("\n  Class groups:")
    for i, g in enumerate(groups, 1):
        print(f"    {i:>3}) #{g.group_id}  {g.group_name}  "
              f"({getattr(g, 'subject_name', '—') or '—'})")
    raw = _input("  Pick # (blank to skip)") or ""
    if not raw:
        return None
    if not raw.isdigit():
        print("    Not a number.")
        return None
    n = int(raw)
    if not (1 <= n <= len(groups)):
        print("    Out of range.")
        return None
    return groups[n - 1].group_id


def _pick_subject() -> str:
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as _sub,
    )
    names = _sub.get_active_names()
    if not names:
        return _input("Subject", allow_empty=False)
    return _pick_from("Subject", names, default=names[0])
