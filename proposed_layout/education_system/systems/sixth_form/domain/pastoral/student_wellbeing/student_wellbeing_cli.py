"""CLI flows for Sixth Form Student Wellbeing."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.systems.sixth_form.domain.pastoral.student_wellbeing import (
    student_wellbeing as data,
)
from education_system.systems.sixth_form.domain.pastoral.student_wellbeing.student_wellbeing import (
    DEFAULT_GOAL_CATEGORY,
    DEFAULT_GOAL_STATUS,
    DEFAULT_RESOURCE_CATEGORY,
    GOAL_CATEGORIES,
    GOAL_STATUSES,
    Goal,
    JournalEntry,
    RESOURCE_CATEGORIES,
    Resource,
    ValidationError,
)
from education_system.systems.sixth_form.domain.learners.students import (
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


def _pick_choice(prompt: str, choices: tuple[str, ...], *,
                 default: str | None = None) -> str:
    print(f"\n  {prompt}:")
    for i, c in enumerate(choices, 1):
        mark = " (default)" if c == default else ""
        print(f"    {i:2d}) {c}{mark}")
    while True:
        raw = _input("Choice (number or name)",
                     default=default or "", allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(choices):
                return choices[n - 1]
        elif raw in choices:
            return raw
        print("    Invalid selection.")


def _today() -> str:
    return _date.today().isoformat()


def _student_id() -> str:
    sid = _input("Student ID", allow_empty=False)
    if _students.get_student(sid) is None:
        print(f"    ✗ No student with id {sid}")
        raise _UserAbort
    return sid


def _student_name(sid: str) -> str:
    s = _students.get_student(sid)
    return s.full_name if s else "(unknown)"


def _opt_int(prompt: str, *, default: str = "") -> str:
    return _input(prompt + " (1-5, blank to skip)", default=default)


def _opt_float(prompt: str, *, default: str = "") -> str:
    return _input(prompt, default=default)


# ── Journal entries ─────────────────────────────────────────────────

def _print_entry(e: JournalEntry) -> None:
    name = _student_name(e.student_id)
    print(f"\n  #{e.entry_id}  {e.entry_date}  {e.student_id} — {name}")
    parts = []
    if e.mood_score is not None:
        parts.append(f"mood {e.mood_score}/5")
    if e.energy_score is not None:
        parts.append(f"energy {e.energy_score}/5")
    if e.stress_score is not None:
        parts.append(f"stress {e.stress_score}/5")
    if e.sleep_hours is not None:
        parts.append(f"sleep {e.sleep_hours:g}h")
    if parts:
        print("    " + " · ".join(parts))
    if e.notes:
        print(f"    notes: {e.notes}")
    if e.gratitude:
        print(f"    grateful for: {e.gratitude}")


def journal_add() -> None:
    print("\n── Add Journal Entry ──")
    try:
        sid = _student_id()
        date = _input("Entry date (YYYY-MM-DD)", default=_today(),
                      allow_empty=False)
        mood = _opt_int("Mood")
        energy = _opt_int("Energy")
        stress = _opt_int("Stress")
        sleep = _opt_float("Sleep hours (blank to skip)")
        notes = _input("Notes")
        gratitude = _input("Grateful for")
        e = data.create_entry({
            "student_id": sid, "entry_date": date,
            "mood_score": mood, "energy_score": energy,
            "stress_score": stress, "sleep_hours": sleep,
            "notes": notes, "gratitude": gratitude,
        })
        print(f"\n  ✓ Created entry #{e.entry_id}")
    except _UserAbort:
        return
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")


def journal_list(*, student_id: str | None = None) -> None:
    rows = data.list_entries(student_id=student_id)
    print(f"\n── Journal Entries ({len(rows)}) ──")
    if not rows:
        print("  (none)")
        return
    for e in rows[:50]:
        _print_entry(e)
    if len(rows) > 50:
        print(f"\n  …and {len(rows) - 50} more")


def journal_view() -> None:
    try:
        eid_raw = _input("Entry id", allow_empty=False)
    except _UserAbort:
        return
    try:
        eid = int(eid_raw)
    except ValueError:
        print("  ✗ Must be a number")
        return
    e = data.get_entry(eid)
    if e is None:
        print(f"  ✗ No entry with id {eid}")
        return
    _print_entry(e)


def journal_edit() -> None:
    print("\n── Edit Journal Entry ──")
    try:
        eid = int(_input("Entry id", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    existing = data.get_entry(eid)
    if existing is None:
        print(f"  ✗ No entry with id {eid}")
        return
    _print_entry(existing)
    try:
        upd: dict[str, Any] = {}
        upd["entry_date"] = _input("Entry date",
                                    default=existing.entry_date)
        upd["mood_score"] = _input(
            "Mood (1-5, blank to clear)",
            default="" if existing.mood_score is None
            else str(existing.mood_score))
        upd["energy_score"] = _input(
            "Energy (1-5, blank to clear)",
            default="" if existing.energy_score is None
            else str(existing.energy_score))
        upd["stress_score"] = _input(
            "Stress (1-5, blank to clear)",
            default="" if existing.stress_score is None
            else str(existing.stress_score))
        upd["sleep_hours"] = _input(
            "Sleep hours (blank to clear)",
            default="" if existing.sleep_hours is None
            else str(existing.sleep_hours))
        upd["notes"] = _input("Notes", default=existing.notes or "")
        upd["gratitude"] = _input("Grateful for",
                                   default=existing.gratitude or "")
        out = data.update_entry(eid, upd)
        print(f"\n  ✓ Updated entry #{out.entry_id}")
    except _UserAbort:
        return
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")


def journal_delete() -> None:
    try:
        eid = int(_input("Entry id to delete", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    e = data.get_entry(eid)
    if e is None:
        print(f"  ✗ No entry with id {eid}")
        return
    _print_entry(e)
    try:
        confirm = _input("Type DELETE to confirm", allow_empty=False)
    except _UserAbort:
        return
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    if data.delete_entry(eid):
        print(f"  ✓ Deleted entry #{eid}")
    else:
        print("  ✗ Nothing deleted")


# ── Goals ──────────────────────────────────────────────────────────

def _print_goal(g: Goal) -> None:
    name = _student_name(g.student_id)
    bar_full = g.progress_pct // 10
    bar = "█" * bar_full + "·" * (10 - bar_full)
    target = g.target_date or "—"
    print(f"\n  #{g.goal_id}  [{g.status}]  {g.student_id} — {name}")
    print(f"    {g.title}")
    print(f"    {g.category}  ·  target {target}  ·  "
          f"{bar} {g.progress_pct}%")
    if g.notes:
        print(f"    notes: {g.notes}")


def goal_add() -> None:
    print("\n── Add Goal ──")
    try:
        sid = _student_id()
        title = _input("Title", allow_empty=False)
        category = _pick_choice(
            "Category", GOAL_CATEGORIES, default=DEFAULT_GOAL_CATEGORY)
        target = _input("Target date (YYYY-MM-DD, blank to skip)")
        pct_raw = _input("Initial progress %", default="0")
        status = _pick_choice(
            "Status", GOAL_STATUSES, default=DEFAULT_GOAL_STATUS)
        notes = _input("Notes")
        g = data.create_goal({
            "student_id": sid, "title": title, "category": category,
            "target_date": target, "progress_pct": pct_raw,
            "status": status, "notes": notes,
        })
        print(f"\n  ✓ Created goal #{g.goal_id}")
    except _UserAbort:
        return
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")


def goal_list(*, open_only: bool = False) -> None:
    rows = data.list_goals(open_only=open_only)
    title = "Open Goals" if open_only else "All Goals"
    print(f"\n── {title} ({len(rows)}) ──")
    if not rows:
        print("  (none)")
        return
    for g in rows[:80]:
        _print_goal(g)
    if len(rows) > 80:
        print(f"\n  …and {len(rows) - 80} more")


def goal_edit() -> None:
    try:
        gid = int(_input("Goal id", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    existing = data.get_goal(gid)
    if existing is None:
        print(f"  ✗ No goal with id {gid}")
        return
    _print_goal(existing)
    try:
        upd: dict[str, Any] = {}
        upd["title"] = _input("Title", default=existing.title)
        upd["category"] = _pick_choice("Category", GOAL_CATEGORIES,
                                        default=existing.category)
        upd["target_date"] = _input(
            "Target date (blank to clear)",
            default=existing.target_date or "")
        upd["progress_pct"] = _input(
            "Progress %", default=str(existing.progress_pct))
        upd["status"] = _pick_choice("Status", GOAL_STATUSES,
                                      default=existing.status)
        upd["notes"] = _input("Notes", default=existing.notes or "")
        out = data.update_goal(gid, upd)
        print(f"\n  ✓ Updated goal #{out.goal_id}")
    except _UserAbort:
        return
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")


def goal_achieve() -> None:
    try:
        gid = int(_input("Goal id to mark Achieved", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    try:
        g = data.mark_goal_achieved(gid)
        print(f"  ✓ Goal #{g.goal_id} marked Achieved")
    except ValidationError as exc:
        print(f"  ✗ {exc}")


def goal_delete() -> None:
    try:
        gid = int(_input("Goal id to delete", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    g = data.get_goal(gid)
    if g is None:
        print(f"  ✗ No goal with id {gid}")
        return
    _print_goal(g)
    try:
        confirm = _input("Type DELETE to confirm", allow_empty=False)
    except _UserAbort:
        return
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    if data.delete_goal(gid):
        print(f"  ✓ Deleted goal #{gid}")


# ── Resources ──────────────────────────────────────────────────────

def _print_resource(r: Resource) -> None:
    name = _student_name(r.student_id)
    print(f"\n  #{r.resource_id}  [{r.category}]  "
          f"{r.student_id} — {name}")
    print(f"    {r.title}")
    if r.url:
        print(f"    {r.url}")
    if r.contact:
        print(f"    contact: {r.contact}")
    if r.notes:
        print(f"    notes: {r.notes}")


def resource_add() -> None:
    print("\n── Add Resource ──")
    try:
        sid = _student_id()
        title = _input("Title", allow_empty=False)
        category = _pick_choice(
            "Category", RESOURCE_CATEGORIES,
            default=DEFAULT_RESOURCE_CATEGORY)
        url = _input("URL (blank to skip)")
        contact = _input("Contact (phone / email / room, blank to skip)")
        notes = _input("Notes")
        r = data.create_resource({
            "student_id": sid, "title": title, "category": category,
            "url": url, "contact": contact, "notes": notes,
        })
        print(f"\n  ✓ Created resource #{r.resource_id}")
    except _UserAbort:
        return
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")


def resource_list() -> None:
    rows = data.list_resources()
    print(f"\n── Resources ({len(rows)}) ──")
    if not rows:
        print("  (none)")
        return
    for r in rows[:80]:
        _print_resource(r)
    if len(rows) > 80:
        print(f"\n  …and {len(rows) - 80} more")


def resource_edit() -> None:
    try:
        rid = int(_input("Resource id", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    existing = data.get_resource(rid)
    if existing is None:
        print(f"  ✗ No resource with id {rid}")
        return
    _print_resource(existing)
    try:
        upd: dict[str, Any] = {}
        upd["title"] = _input("Title", default=existing.title)
        upd["category"] = _pick_choice(
            "Category", RESOURCE_CATEGORIES, default=existing.category)
        upd["url"] = _input("URL (blank to clear)",
                             default=existing.url or "")
        upd["contact"] = _input("Contact (blank to clear)",
                                 default=existing.contact or "")
        upd["notes"] = _input("Notes", default=existing.notes or "")
        out = data.update_resource(rid, upd)
        print(f"\n  ✓ Updated resource #{out.resource_id}")
    except _UserAbort:
        return
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")


def resource_delete() -> None:
    try:
        rid = int(_input("Resource id to delete", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    r = data.get_resource(rid)
    if r is None:
        print(f"  ✗ No resource with id {rid}")
        return
    _print_resource(r)
    try:
        confirm = _input("Type DELETE to confirm", allow_empty=False)
    except _UserAbort:
        return
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    if data.delete_resource(rid):
        print(f"  ✓ Deleted resource #{rid}")


# ── Per-student summary ────────────────────────────────────────────

def per_student() -> None:
    print("\n── Student Wellbeing Summary ──")
    try:
        sid = _student_id()
    except _UserAbort:
        return
    s = data.per_student_summary(sid)
    name = _student_name(sid)
    print(f"\n  {sid} — {name}")
    print(f"    Entries: {s.entry_count}    "
          f"Goals: {s.goal_count_open} open / "
          f"{s.goal_count_achieved} achieved    "
          f"Resources: {s.resource_count}")
    if s.latest_entry_date:
        print(f"\n  Latest entry ({s.latest_entry_date}):")
        bits = []
        if s.latest_mood is not None:
            bits.append(f"mood {s.latest_mood}/5")
        if s.latest_energy is not None:
            bits.append(f"energy {s.latest_energy}/5")
        if s.latest_stress is not None:
            bits.append(f"stress {s.latest_stress}/5")
        if s.latest_sleep_hours is not None:
            bits.append(f"sleep {s.latest_sleep_hours:g}h")
        if bits:
            print("    " + " · ".join(bits))
    if s.entry_count:
        bits = []
        if s.avg_mood is not None:
            bits.append(f"mood {s.avg_mood}")
        if s.avg_energy is not None:
            bits.append(f"energy {s.avg_energy}")
        if s.avg_stress is not None:
            bits.append(f"stress {s.avg_stress}")
        if s.avg_sleep_hours is not None:
            bits.append(f"sleep {s.avg_sleep_hours}h")
        if bits:
            print(f"\n  Averages: {' · '.join(bits)}")


def overall_summary() -> None:
    print("\n── Student Wellbeing Overview ──")
    s = data.summary()
    print(f"  Entries:    {s.total_entries}  "
          f"(low-mood {s.low_mood_count}, "
          f"high-stress {s.high_stress_count})")
    print(f"  Goals:      {s.total_goals}  "
          f"(active {s.goals_active}, paused {s.goals_paused}, "
          f"achieved {s.goals_achieved}, abandoned {s.goals_abandoned})")
    print(f"  Resources:  {s.total_resources}")
    print(f"  Students engaged: {s.students_engaged}")
    if any(s.by_goal_category.values()):
        print("\n  Goals by category:")
        for cat, n in s.by_goal_category.items():
            if n:
                print(f"    {cat:18s} {n}")
    if any(s.by_resource_category.values()):
        print("\n  Resources by category:")
        for cat, n in s.by_resource_category.items():
            if n:
                print(f"    {cat:18s} {n}")


# ── Menu ───────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None] | None]] = [
    ("── Journal ──",            None),
    ("Add entry",                 journal_add),
    ("List entries",              journal_list),
    ("View entry",                journal_view),
    ("Edit entry",                journal_edit),
    ("Delete entry",              journal_delete),
    ("── Goals ──",              None),
    ("Add goal",                  goal_add),
    ("List open goals",           lambda: goal_list(open_only=True)),
    ("List all goals",            lambda: goal_list(open_only=False)),
    ("Edit goal",                 goal_edit),
    ("Mark goal Achieved",        goal_achieve),
    ("Delete goal",               goal_delete),
    ("── Resources ──",          None),
    ("Add resource",              resource_add),
    ("List resources",            resource_list),
    ("Edit resource",             resource_edit),
    ("Delete resource",           resource_delete),
    ("── Summary ──",            None),
    ("Per-student summary",       per_student),
    ("Overview",                  overall_summary),
]


def run() -> None:
    while True:
        print("\n── Student Wellbeing ──")
        for i, (label, handler) in enumerate(_MENU, 1):
            if handler is None:
                print(f"   {label}")
            else:
                print(f"  {i:2d}) {label}")
        print("   0) Back")
        try:
            choice = input("Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if handler is None:
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Student Wellbeing CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Student Wellbeing":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Student Wellbeing CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
