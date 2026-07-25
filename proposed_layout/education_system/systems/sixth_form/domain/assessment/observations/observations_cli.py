"""CLI flows for Sixth Form Observations."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.assessment.observations import (
    observations as data,
)
from education_system.systems.sixth_form.domain.assessment.observations.observations import (
    DEFAULT_FOCUS_AREA,
    DEFAULT_OBSERVATION_TYPE,
    DEFAULT_STATUS,
    FOCUS_AREAS,
    JUDGEMENTS,
    OBSERVATION_TYPES,
    Observation,
    STATUSES,
    ValidationError,
    YEAR_GROUPS,
    judgement_label,
)

logger = logging.getLogger(__name__)


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


def _pick_observation() -> Observation:
    rows = data.list_observations()
    if not rows:
        print("    No observations yet.")
        raise _UserAbort
    print("\n  Observations:")
    for i, o in enumerate(rows, 1):
        flag = "!" if o.follow_up_overdue else " "
        print(f"    {i:>3}){flag}#{o.observation_id}  "
              f"{o.observation_date}  "
              f"{o.observed_teacher[:18]:<18}  "
              f"{o.observation_type[:14]:<14}  "
              f"J={o.judgement or '—'}  [{o.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((o for o in rows
                            if o.observation_id == n), None)
            if match:
                return match
        print("    No matching observation.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_observations(rows: list[Observation]) -> None:
    if not rows:
        print("\n  (no observations)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Observer':<18}  "
          f"{'Teacher':<18}  {'Type':<14}  "
          f"{'Focus':<22}  J  {'Status':<14}  Follow-up")
    print("  " + "-" * 130)
    for o in rows:
        fu = ("Yes" if o.follow_up_required else "—")
        if o.follow_up_overdue:
            fu = f"OVERDUE ({o.follow_up_due})"
        print(f"  {o.observation_id:>4}  "
              f"{o.observation_date:<10}  "
              f"{o.observer[:18]:<18}  "
              f"{o.observed_teacher[:18]:<18}  "
              f"{o.observation_type[:14]:<14}  "
              f"{(o.focus_area or '—')[:22]:<22}  "
              f"{o.judgement or '—'}  {o.status:<14}  {fu}")
    print(f"\n  {len(rows)} observation(s).")


def _print_observation_full(o: Observation) -> None:
    print()
    print(f"    #{o.observation_id}")
    print(f"    Date / time      : {o.observation_date}  "
          f"{o.observation_time or '—'}")
    print(f"    Duration         : "
          f"{o.duration_minutes or '—'} mins")
    print(f"    Observer         : {o.observer}")
    print(f"    Observed teacher : {o.observed_teacher}")
    print(f"    Type             : {o.observation_type}")
    print(f"    Focus area       : {o.focus_area or '—'}")
    print(f"    Subject          : {o.subject_name or '—'}")
    print(f"    Class group      : "
          f"#{o.class_group_id or '—'}  {o.class_group_label or '—'}")
    print(f"    Year group       : {o.year_group or '—'}")
    print(f"    Room             : {o.room or '—'}")
    print(f"    Judgement        : "
          f"{o.judgement or '—'}  ({o.judgement_label})")
    print(f"    Status           : {o.status}")
    print(f"    Shared with tchr : "
          f"{'yes' if o.shared_with_teacher else 'no'}")
    if o.follow_up_required:
        print(f"    Follow-up        : due "
              f"{o.follow_up_due or '—'} by {o.follow_up_by or '—'}"
              + ("  (overdue)" if o.follow_up_overdue else ""))
    for label, val in (
            ("Strengths",          o.strengths),
            ("Areas to develop",   o.areas_to_develop),
            ("Student engagement", o.student_engagement),
            ("Student progress",   o.student_progress),
            ("Teacher response",   o.teacher_response),
            ("Notes",              o.notes),
    ):
        if val:
            print()
            print(f"    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Observations ═══")
    _print_observations(data.list_observations())
    _pause()


def list_open() -> None:
    print("\n═══ Open Observations ═══")
    _print_observations(data.list_observations(open_only=True))
    _pause()


def list_follow_up() -> None:
    print("\n═══ Open with Follow-Up ═══")
    _print_observations(data.list_observations(
        follow_up_only=True, open_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Follow-Up ═══")
    _print_observations(data.list_observations(
        follow_up_overdue=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Observations ═══")
    try:
        observer = _input("Observer contains") or None
        teacher = _input("Observed teacher contains") or None
        otype = _input(
            f"Type ({'/'.join(OBSERVATION_TYPES[:3])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        focus = _input(f"Focus ({'/'.join(FOCUS_AREAS[:3])}…)") or None
        year = _input(f"Year ({'/'.join(YEAR_GROUPS)})") or None
        judgement_raw = _input("Judgement (1-4)") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    judgement: int | None = None
    if judgement_raw:
        try:
            judgement = int(judgement_raw)
        except ValueError:
            print("  ✗ Judgement must be 1-4.")
            _pause()
            return
    try:
        rows = data.list_observations(
            observer_like=observer, teacher_like=teacher,
            observation_type=otype, status=status,
            focus_area=focus, year_group=year,
            judgement=judgement,
            date_from=df, date_to=dt2,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_observations(rows)
    _pause()


def per_teacher_flow() -> None:
    print("\n═══ Per-Teacher Observations ═══")
    try:
        teacher = _input("Teacher name", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.observations_for_teacher(teacher)
    _print_observations(rows)
    tsum = data.teacher_summary(teacher)
    print(f"\n  Summary for {teacher!r}:")
    print(f"    Total            : {tsum.total}")
    print(f"    Average judgement: "
          f"{tsum.average_judgement if tsum.average_judgement is not None else '—'}")
    print(f"    Most recent      : {tsum.most_recent or '—'}")
    print("    By judgement:")
    for j in JUDGEMENTS:
        n = tsum.by_judgement.get(j, 0)
        if n:
            print(f"      {j}  {judgement_label(j):<24} : {n}")
    _pause()


def view_flow() -> None:
    print("\n═══ View Observation ═══")
    try:
        o = _pick_observation()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_observation_full(o)
    _pause()


def _collect_form(existing: Observation | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["observer"] = _input(
        "Observer",
        default=(existing.observer if is_edit else ""),
        allow_empty=False)
    payload["observed_teacher"] = _input(
        "Observed teacher",
        default=(existing.observed_teacher if is_edit else ""),
        allow_empty=False)
    payload["observation_date"] = _input(
        "Date (YYYY-MM-DD)",
        default=(existing.observation_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["observation_time"] = _input(
        "Time (HH:MM)",
        default=(existing.observation_time[:5]
                  if is_edit and existing.observation_time
                  else ""))
    payload["duration_minutes"] = _input(
        "Duration (mins)",
        default=(str(existing.duration_minutes)
                  if is_edit and existing.duration_minutes is not None
                  else "30"))
    payload["observation_type"] = _pick_from(
        "Type", list(OBSERVATION_TYPES),
        default=(existing.observation_type if is_edit
                  else DEFAULT_OBSERVATION_TYPE))
    payload["focus_area"] = _pick_from(
        "Focus area", [""] + list(FOCUS_AREAS),
        default=(existing.focus_area if is_edit
                  else DEFAULT_FOCUS_AREA))
    payload["subject_name"] = _input(
        "Subject",
        default=(existing.subject_name or "") if is_edit else "")
    payload["class_group_id"] = _input(
        "Class group id (optional)",
        default=(str(existing.class_group_id)
                  if is_edit and existing.class_group_id else ""))
    payload["class_group_label"] = _input(
        "Class group label",
        default=(existing.class_group_label or "")
        if is_edit else "")
    payload["year_group"] = _pick_from(
        "Year group", [""] + list(YEAR_GROUPS),
        default=(existing.year_group if is_edit else ""))
    payload["room"] = _input(
        "Room",
        default=(existing.room or "") if is_edit else "")
    payload["judgement"] = _input(
        "Judgement (1-4, 1=Outstanding)",
        default=(str(existing.judgement)
                  if is_edit and existing.judgement is not None
                  else ""))
    try:
        payload["strengths"] = _multiline(
            "Strengths",
            default=(existing.strengths or "") if is_edit else "")
        payload["areas_to_develop"] = _multiline(
            "Areas to develop",
            default=(existing.areas_to_develop or "")
            if is_edit else "")
        payload["student_engagement"] = _multiline(
            "Student engagement",
            default=(existing.student_engagement or "")
            if is_edit else "")
        payload["student_progress"] = _multiline(
            "Student progress",
            default=(existing.student_progress or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["follow_up_required"] = _yes_no(
        "Follow-up required?",
        default=(existing.follow_up_required
                  if is_edit else False))
    if payload["follow_up_required"]:
        payload["follow_up_due"] = _input(
            "Follow-up due (YYYY-MM-DD)",
            default=(existing.follow_up_due or "")
            if is_edit else "")
        payload["follow_up_by"] = _input(
            "Follow-up by",
            default=(existing.follow_up_by or "")
            if is_edit else "")
    payload["shared_with_teacher"] = _yes_no(
        "Shared with teacher?",
        default=(existing.shared_with_teacher
                  if is_edit else False))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_observation() -> None:
    print("\n═══ New Observation ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        o = data.create_observation(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created observation #{o.observation_id}")
    _pause()


def edit_observation() -> None:
    print("\n═══ Edit Observation ═══")
    try:
        o = _pick_observation()
        payload = _collect_form(o)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_observation(o.observation_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{o.observation_id}")
    _pause()


def share_flow() -> None:
    print("\n═══ Share with Teacher ═══")
    try:
        o = _pick_observation()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.share(o.observation_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{o.observation_id} shared")
    _pause()


def record_response_flow() -> None:
    print("\n═══ Record Teacher Response ═══")
    try:
        o = _pick_observation()
        response = _multiline("Teacher response")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_teacher_response(o.observation_id,
                                          response=response)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Response recorded; #{o.observation_id} → Acknowledged")
    _pause()


def close_flow() -> None:
    print("\n═══ Close Observation ═══")
    try:
        o = _pick_observation()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_observation(o.observation_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{o.observation_id} → Closed")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        o = _pick_observation()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=o.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(o.observation_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{o.observation_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete Observation ═══")
    try:
        o = _pick_observation()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete observation #{o.observation_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_observation(o.observation_id):
        print(f"\n  ✓ Deleted #{o.observation_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Observations Summary ═══")
    summ = data.summary()
    print(f"\n  Total observations  : {summ.total}")
    print(f"  Open                : {summ.open_count}")
    print(f"  Follow-ups open     : {summ.follow_up_open}")
    print(f"  Follow-ups overdue  : {summ.follow_up_overdue}")
    print(f"  Average judgement   : "
          f"{summ.average_judgement if summ.average_judgement is not None else '—'}")
    print(f"  Distinct observers  : {summ.distinct_observers}")
    print(f"  Distinct teachers   : {summ.distinct_teachers}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By type:")
    for t in OBSERVATION_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<18} : {n}")
    print("\n  By judgement:")
    for j in JUDGEMENTS:
        n = summ.by_judgement.get(j, 0)
        if n:
            print(f"    {j}  {judgement_label(j):<24} : {n}")
    if summ.by_focus:
        print("\n  By focus area:")
        for f, n in list(summ.by_focus.items())[:10]:
            print(f"    {f:<24} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",                list_all),
    ("List open",               list_open),
    ("Follow-up open",          list_follow_up),
    ("Follow-up overdue",       list_overdue),
    ("Filter",                  filter_flow),
    ("Per-teacher",             per_teacher_flow),
    ("View",                    view_flow),
    ("─" * 6,                   lambda: None),
    ("New observation",         new_observation),
    ("Edit observation",        edit_observation),
    ("Share with teacher",      share_flow),
    ("Record teacher response", record_response_flow),
    ("Close",                   close_flow),
    ("Change status",           set_status_flow),
    ("Delete",                  delete_flow),
    ("─" * 6,                   lambda: None),
    ("Summary",                 summary_flow),
]


def run() -> None:
    while True:
        print("\n── Observations ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
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
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Observations CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Observations":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Observations CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
