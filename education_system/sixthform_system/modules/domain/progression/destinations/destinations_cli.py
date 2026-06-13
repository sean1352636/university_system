"""CLI flows for KS5 Destinations."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.sixthform_system.modules.domain.progression.destinations import (
    destinations as data,
)
from education_system.sixthform_system.modules.domain.progression.destinations.destinations import (
    CHECKPOINTS,
    CHECKPOINT_LABELS,
    CONFIRMED_VIA,
    DEFAULT_CHECKPOINT,
    DEFAULT_DESTINATION_TYPE,
    DESTINATION_TYPES,
    DestinationRecord,
    SALARY_BANDS,
    STUDY_LEVELS,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as _students,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


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


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.'; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None,
                allow_blank: bool = False) -> str:
    print(f"\n  {label}:")
    opts = ([""] + options) if allow_blank else options
    for i, opt in enumerate(opts, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(opts)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(opts)):
            print("    Out of range.")
            continue
        return opts[n - 1]


def _pick_student() -> str:
    rows = _students.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.student_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
        match = next((s for s in rows if s.student_id == raw), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_record() -> DestinationRecord:
    rows = data.list_records()
    if not rows:
        print("    No destination records yet.")
        raise _UserAbort
    names = {s.student_id: s.full_name for s in _students.list_students()}
    print("\n  Destination records:")
    for i, r in enumerate(rows, 1):
        name = names.get(r.student_id, "(unknown)")
        print(f"    {i:>3}) #{r.record_id:<4}  {r.student_id:<12}  "
              f"{name[:22]:<22}  {r.checkpoint:<8}  "
              f"{r.destination_type[:17]:<17}  "
              f"{r.display_target()[:40]}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or record id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows if r.record_id == n), None)
            if match:
                return match
        print("    No matching record.")


# ── Rendering ────────────────────────────────────────────────────

def _print_table(rows: list[data.DestinationRow]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<12} {'Name':<22}  "
          f"{'Checkpoint':<10}  {'Type':<18}  "
          f"{'Target':<40}  Confirmed")
    print("  " + "-" * 130)
    for r in rows:
        d = r.record
        flag = "+" if d.is_positive else " "
        target = d.display_target()
        print(f"  {d.record_id:>4}{flag} {d.student_id:<12} "
              f"{r.student_name[:22]:<22}  "
              f"{d.checkpoint:<10}  "
              f"{d.destination_type[:18]:<18}  "
              f"{target[:40]:<40}  "
              f"{d.confirmed_date or '—'}")
    print(f"\n  {len(rows)} record(s).  (+ = positive sustained destination)")


def _print_full(d: DestinationRecord) -> None:
    s = _students.get_student(d.student_id)
    name = getattr(s, "full_name", None) or "(unknown)"
    print()
    print(f"    #{d.record_id}  Student {d.student_id} ({name})")
    print(f"    Checkpoint       : {d.checkpoint}  "
          f"({CHECKPOINT_LABELS.get(d.checkpoint, '?')})")
    print(f"    Destination type : {d.destination_type}"
          f"{'  [positive]' if d.is_positive else ''}")
    print(f"    Institution      : {d.institution or '—'}")
    print(f"    Course           : {d.course or '—'}")
    print(f"    Study level      : {d.study_level or '—'}")
    print(f"    Employer         : {d.employer or '—'}")
    print(f"    Role             : {d.role or '—'}")
    print(f"    Salary band      : {d.salary_band or '—'}")
    print(f"    Start date       : {d.start_date or '—'}")
    print(f"    Confirmed        : {d.confirmed_via or '—'}"
          f"  on {d.confirmed_date or '—'}")
    if d.notes:
        print("\n    Notes:")
        for line in d.notes.splitlines():
            print(f"      {line}")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Destination Records ═══")
    _print_table(data.list_records_with_detail())
    _pause()


def list_by_checkpoint() -> None:
    try:
        cp = _pick_from("Checkpoint", list(CHECKPOINTS))
        print(f"\n═══ Records at: {cp} "
              f"({CHECKPOINT_LABELS[cp]}) ═══")
        _print_table(data.list_records_with_detail(checkpoint=cp))
        _pause()
    except _UserAbort:
        return


def list_by_type() -> None:
    try:
        t = _pick_from("Destination type", list(DESTINATION_TYPES))
        print(f"\n═══ Records of type: {t} ═══")
        _print_table(data.list_records_with_detail(destination_type=t))
        _pause()
    except _UserAbort:
        return


def list_missing() -> None:
    try:
        cp = _pick_from("Checkpoint", list(CHECKPOINTS),
                          default=DEFAULT_CHECKPOINT)
        missing = data.students_missing_at(cp)
        names = {s.student_id: s.full_name
                  for s in _students.list_students()}
        print(f"\n═══ Students missing destination at {cp} ═══\n")
        if not missing:
            print("  (none — everyone is captured)")
        else:
            for sid in missing:
                print(f"    {sid:<12}  {names.get(sid, '(unknown)')}")
            print(f"\n  {len(missing)} student(s) missing.")
        _pause()
    except _UserAbort:
        return


def view_student_record() -> None:
    try:
        sid = _pick_student()
        rows = data.records_for_student(sid)
        if not rows:
            print(f"\n  (no destination records for {sid})")
        else:
            print(f"\n═══ Records for student {sid} ═══")
            for r in rows:
                _print_full(r)
        _pause()
    except _UserAbort:
        return


def view_record() -> None:
    try:
        r = _pick_record()
        _print_full(r)
        _pause()
    except _UserAbort:
        return


def save_record_flow() -> None:
    print("\n═══ Save / Update Destination Record ═══")
    try:
        sid = _pick_student()
        cp = _pick_from("Checkpoint", list(CHECKPOINTS),
                          default=DEFAULT_CHECKPOINT)
        existing = data.get_record_for(sid, cp)
        if existing is not None:
            print(f"\n  (Existing {cp} record found — editing #"
                  f"{existing.record_id}.)")
        dtype = _pick_from(
            "Destination type", list(DESTINATION_TYPES),
            default=(existing.destination_type if existing
                       else DEFAULT_DESTINATION_TYPE))
        institution = _input("Institution",
                                default=(existing.institution if existing
                                          else "") or "")
        course = _input("Course",
                         default=(existing.course if existing else "") or "")
        level = _pick_from(
            "Study level", list(STUDY_LEVELS), allow_blank=True,
            default=(existing.study_level if existing else ""))
        employer = _input("Employer",
                            default=(existing.employer if existing
                                      else "") or "")
        role = _input("Role",
                       default=(existing.role if existing else "") or "")
        salary = _pick_from(
            "Salary band", list(SALARY_BANDS), allow_blank=True,
            default=(existing.salary_band if existing else ""))
        start = _input("Start date (YYYY-MM-DD)",
                        default=(existing.start_date if existing
                                  else "") or "")
        via = _pick_from(
            "Confirmed via", list(CONFIRMED_VIA), allow_blank=True,
            default=(existing.confirmed_via if existing else ""))
        confirmed = _input(
            "Confirmed date (YYYY-MM-DD)",
            default=(existing.confirmed_date if existing
                      else "") or "")
        notes = _multiline("Notes",
                            default=(existing.notes if existing
                                      else "") or "")
        out = data.save_record({
            "student_id": sid, "checkpoint": cp,
            "destination_type": dtype, "institution": institution,
            "course": course, "study_level": level,
            "employer": employer, "role": role,
            "salary_band": salary, "start_date": start,
            "confirmed_via": via, "confirmed_date": confirmed,
            "notes": notes,
        })
        print(f"\n  ✓ Saved record #{out.record_id} "
              f"({out.checkpoint} = {out.destination_type}).")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("save_record_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def delete_record_flow() -> None:
    print("\n═══ Delete Destination Record ═══")
    try:
        r = _pick_record()
        _print_full(r)
        if not _yes_no("\n  Delete this record?"):
            print("  (cancelled)")
            return
        if data.delete_record(r.record_id):
            print(f"\n  ✓ Deleted record #{r.record_id}.")
        else:
            print("\n  ✗ Delete failed.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except Exception as e:
        logger.exception("delete_record_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def show_summary() -> None:
    print("\n═══ Destinations Summary ═══")
    try:
        s = data.summary()
        print(f"\n  Total records              : {s.total_records}")
        print(f"  Students captured @ LEAVING: {s.students_with_leaving}")
        print(f"  Students MISSING @ LEAVING : {s.students_missing_leaving}")
        print(f"\n  Positive sustained destinations:")
        print(f"    @ LEAVING : {s.positive_at_leaving}")
        print(f"    @ +6  mth : {s.positive_at_plus_6}")
        print(f"    @ +12 mth : {s.positive_at_plus_12}")
        print("\n  Records by checkpoint:")
        for cp, n in s.by_checkpoint.items():
            print(f"    {cp:<10} {n:>4}  ({CHECKPOINT_LABELS[cp]})")
        print("\n  By destination type:")
        for d, n in s.by_destination_type.items():
            if n:
                print(f"    {d:<22} {n:>4}")
        if any(n for n in s.by_level_at_leaving.values()):
            print("\n  Study level at LEAVING:")
            for lvl, n in s.by_level_at_leaving.items():
                if n:
                    print(f"    {lvl:<14} {n:>4}")
        _pause()
    except Exception as e:
        logger.exception("show_summary failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Menu ─────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all records",             list_all),
    ("List by checkpoint",            list_by_checkpoint),
    ("List by destination type",      list_by_type),
    ("Students missing destination",  list_missing),
    ("View student's records",        view_student_record),
    ("View record (detail)",          view_record),
    ("Save / update record",          save_record_flow),
    ("Delete record",                 delete_record_flow),
    ("Summary report",                show_summary),
]


def run() -> None:
    while True:
        print("\n══════ KS5 Destinations ══════")
        for i, (label, _fn) in enumerate(_MENU, 1):
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
        _label, fn = _MENU[int(choice) - 1]
        try:
            fn()
        except _UserAbort:
            print("\n  (cancelled)")
        except Exception as e:
            logger.exception("Destinations CLI flow crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Destinations":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Destinations CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
