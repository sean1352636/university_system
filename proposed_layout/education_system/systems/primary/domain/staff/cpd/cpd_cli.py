"""CLI flows for Primary School CPD."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.primary.domain.staff.cpd import (
    cpd as data,
)
from education_system.systems.primary.domain.staff.cpd.cpd import (
    ACTIVITY_STATUSES,
    ACTIVITY_TYPES,
    Activity,
    DEFAULT_ACTIVITY_STATUS,
    DEFAULT_ACTIVITY_TYPE,
    DEFAULT_RECORD_STATUS,
    RATINGS,
    RECORD_STATUSES,
    Record,
    ValidationError,
    rating_label,
)
from education_system.systems.primary.domain.staff import (
    staff as _staff,
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
            return _input(prompt, default=default,
                            allow_empty=False)
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
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_staff() -> str:
    rows = _staff.list_staff()
    if not rows:
        print("    No staff.")
        raise _UserAbort
    print("\n  Staff:")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.staff_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].staff_id
        match = next((s for s in rows
                        if s.staff_id == raw.upper()), None)
        if match:
            return match.staff_id
        print("    No matching staff.")


def _pick_activity(*, optional: bool = False) -> Activity | None:
    rows = data.list_activities()
    if not rows:
        if optional:
            return None
        print("    No activities yet.")
        raise _UserAbort
    print("\n  Activities:")
    if optional:
        print("    0) (none)")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.activity_id}  "
              f"{a.activity_date}  {a.activity_type[:14]:<14}  "
              f"{a.title[:36]:<36}  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)}"
                      + (" (0 for none)" if optional else "")
                      + " (or id)",
                      allow_empty=optional)
        if optional and (not raw or raw == "0"):
            return None
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.activity_id == n), None)
            if match:
                return match
        print("    No matching activity.")


def _pick_record() -> Record:
    rows = data.list_records()
    if not rows:
        print("    No records yet.")
        raise _UserAbort
    print("\n  Records:")
    for i, r in enumerate(rows, 1):
        print(f"    {i:>3}) #{r.record_id}  "
              f"{r.staff_id:<12}  "
              f"{(r.activity_title_cache or '—')[:30]:<30}  "
              f"[{r.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.record_id == n), None)
            if match:
                return match
        print("    No matching record.")


# ── Activity flows ───────────────────────────────────────

def _print_activities(rows: list[Activity]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Type':<18}  "
          f"{'Title':<36}  Hrs    "
          f"{'Provider':<18}  Recs  Status")
    print("  " + "-" * 120)
    for a in rows:
        nrec = data.record_count(a.activity_id)
        print(f"  {a.activity_id:>4}  {a.activity_date:<10}  "
              f"{a.activity_type[:18]:<18}  "
              f"{a.title[:36]:<36}  "
              f"{(a.hours if a.hours is not None else '—'):>5}  "
              f"{(a.provider or '—')[:18]:<18}  "
              f"{nrec:>4}  {a.status}")
    print(f"\n  {len(rows)} activity(ies).")


def activities_list() -> None:
    print("\n═══ All Activities ═══")
    _print_activities(data.list_activities())
    _pause()


def activities_upcoming() -> None:
    print("\n═══ Upcoming ═══")
    _print_activities(data.list_activities(upcoming_only=True))
    _pause()


def activities_completed() -> None:
    print("\n═══ Completed ═══")
    _print_activities(data.list_activities(completed_only=True))
    _pause()


def activities_filter() -> None:
    print("\n═══ Filter ═══")
    try:
        at = _input(
            f"Type ({'/'.join(ACTIVITY_TYPES[:3])}…)") or None
        status = _input(
            f"Status ({'/'.join(ACTIVITY_STATUSES[:3])}…)") or None
        provider = _input("Provider contains") or None
        title = _input("Title contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_activities(activity_type=at,
                                          status=status,
                                          provider_like=provider,
                                          title_like=title,
                                          date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_activities(rows)
    _pause()


def _collect_activity_form(
        existing: Activity | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["provider"] = _input(
        "Provider",
        default=(existing.provider or "") if is_edit else "")
    payload["activity_type"] = _pick_from(
        "Type", list(ACTIVITY_TYPES),
        default=(existing.activity_type if is_edit
                  else DEFAULT_ACTIVITY_TYPE))
    payload["activity_date"] = _input(
        "Activity date (YYYY-MM-DD)",
        default=(existing.activity_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date or "") if is_edit else "")
    payload["hours"] = _input(
        "Hours",
        default=(str(existing.hours)
                  if is_edit and existing.hours is not None
                  else ""))
    payload["cost"] = _input(
        "Cost (£)",
        default=(str(existing.cost)
                  if is_edit and existing.cost is not None
                  else ""))
    payload["certificated"] = _yes_no(
        "Certificated?",
        default=(existing.certificated if is_edit else False))
    payload["accreditor"] = _input(
        "Accreditor",
        default=(existing.accreditor or "")
        if is_edit else "")
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    payload["capacity"] = _input(
        "Capacity",
        default=(str(existing.capacity)
                  if is_edit and existing.capacity is not None
                  else ""))
    payload["organiser"] = _input(
        "Organiser",
        default=(existing.organiser or "") if is_edit else "")
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "")
            if is_edit else "")
        payload["outcomes"] = _multiline(
            "Outcomes",
            default=(existing.outcomes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["status"] = _pick_from(
        "Status", list(ACTIVITY_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_ACTIVITY_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def activities_new() -> None:
    print("\n═══ New Activity ═══")
    try:
        payload = _collect_activity_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_activity(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created activity #{a.activity_id}")
    _pause()


def activities_edit() -> None:
    print("\n═══ Edit Activity ═══")
    try:
        a = _pick_activity()
        if a is None:
            return
        payload = _collect_activity_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_activity(a.activity_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.activity_id}")
    _pause()


def activities_mark_completed() -> None:
    print("\n═══ Mark Completed ═══")
    try:
        a = _pick_activity()
        if a is None:
            return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_activity_completed(a.activity_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.activity_id} → Completed")
    _pause()


def activities_set_status() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_activity()
        if a is None:
            return
        new_status = _pick_from("New status",
                                  list(ACTIVITY_STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_activity_status(a.activity_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.activity_id} → {new_status}")
    _pause()


def activities_delete() -> None:
    print("\n═══ Delete Activity ═══")
    try:
        a = _pick_activity()
        if a is None:
            return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete activity #{a.activity_id}? "
              "(records keep history) Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_activity(a.activity_id):
        print(f"\n  ✓ Deleted #{a.activity_id}")
    _pause()


# ── Record flows ─────────────────────────────────────────

def _print_records(rows: list[Record]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Staff':<12}  "
          f"{'Activity':<32}  {'Booked':<10}  "
          f"{'Attended':<10}  Hrs    Rating  Cert  "
          f"{'Status':<14}")
    print("  " + "-" * 130)
    for r in rows:
        rating = (rating_label(r.evaluation_rating)[:6]
                    if r.evaluation_rating else "—")
        cert = "yes" if r.certificate_filed else (
            "rcvd" if r.certificate_received else "—")
        print(f"  {r.record_id:>4}  {r.staff_id:<12}  "
              f"{(r.activity_title_cache or '—')[:32]:<32}  "
              f"{r.booked_on:<10}  "
              f"{(r.attended_on or '—'):<10}  "
              f"{(r.hours_completed if r.hours_completed is not None else '—'):>5}  "
              f"{rating:<7}  {cert:<5}  {r.status}")
    print(f"\n  {len(rows)} record(s).")


def records_list() -> None:
    print("\n═══ All Records ═══")
    _print_records(data.list_records())
    _pause()


def records_awaiting_cert() -> None:
    print("\n═══ Awaiting Certificate ═══")
    _print_records(data.list_records(awaiting_certificate=True))
    _pause()


def records_completed() -> None:
    print("\n═══ Completed Records ═══")
    _print_records(data.list_records(completed_only=True))
    _pause()


def records_per_staff() -> None:
    print("\n═══ Per-Staff ═══")
    try:
        sid = _pick_staff()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_records(data.records_for_staff(sid))
    _pause()


def records_for_activity() -> None:
    print("\n═══ Records for Activity ═══")
    try:
        a = _pick_activity()
        if a is None:
            return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_records(data.list_records(activity_id=a.activity_id))
    _pause()


def records_filter() -> None:
    print("\n═══ Filter Records ═══")
    try:
        sid = _input("Staff id") or None
        status = _input(
            f"Status ({'/'.join(RECORD_STATUSES[:3])}…)") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_records(staff_id=sid, status=status,
                                       date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_records(rows)
    _pause()


def _collect_record_form(
        existing: Record | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["staff_id"] = existing.staff_id
        payload["activity_id"] = existing.activity_id
    else:
        payload["staff_id"] = _pick_staff()
        if _yes_no("Link to an activity?", default=True):
            a = _pick_activity(optional=True)
            payload["activity_id"] = a.activity_id if a else None
        else:
            payload["activity_id"] = None
    payload["booked_on"] = _input(
        "Booked on (YYYY-MM-DD)",
        default=(existing.booked_on if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["attended_on"] = _input(
        "Attended on (YYYY-MM-DD)",
        default=(existing.attended_on or "")
        if is_edit else "")
    payload["hours_completed"] = _input(
        "Hours completed",
        default=(str(existing.hours_completed)
                  if is_edit
                  and existing.hours_completed is not None
                  else ""))
    payload["evaluation_rating"] = _input(
        "Evaluation rating (1-5)",
        default=(str(existing.evaluation_rating)
                  if is_edit
                  and existing.evaluation_rating is not None
                  else ""))
    try:
        payload["evaluation_notes"] = _multiline(
            "Evaluation notes",
            default=(existing.evaluation_notes or "")
            if is_edit else "")
        payload["impact_on_practice"] = _multiline(
            "Impact on practice",
            default=(existing.impact_on_practice or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["certificate_received"] = _yes_no(
        "Certificate received?",
        default=(existing.certificate_received
                  if is_edit else False))
    payload["certificate_filed"] = _yes_no(
        "Certificate filed?",
        default=(existing.certificate_filed
                  if is_edit else False))
    payload["certificate_ref"] = _input(
        "Certificate reference",
        default=(existing.certificate_ref or "")
        if is_edit else "")
    payload["cost_to_staff"] = _input(
        "Cost to staff (£)",
        default=(str(existing.cost_to_staff)
                  if is_edit
                  and existing.cost_to_staff is not None
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(RECORD_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_RECORD_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def records_new() -> None:
    print("\n═══ New Record ═══")
    try:
        payload = _collect_record_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_record(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created record #{r.record_id}")
    _pause()


def records_edit() -> None:
    print("\n═══ Edit Record ═══")
    try:
        r = _pick_record()
        payload = _collect_record_form(r)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_record(r.record_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{r.record_id}")
    _pause()


def records_mark_attended() -> None:
    print("\n═══ Mark Attended ═══")
    try:
        r = _pick_record()
        when = _input("Attended on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
        hours_raw = _input("Hours completed",
                              default=str(r.hours_completed)
                              if r.hours_completed is not None
                              else "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    hours = None
    if hours_raw:
        try:
            hours = float(hours_raw)
        except ValueError:
            print("  ✗ Hours must be a number.")
            _pause()
            return
    try:
        data.mark_attended(r.record_id, attended_on=when,
                              hours=hours)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{r.record_id} → Attended")
    _pause()


def records_evaluate() -> None:
    print("\n═══ Record Evaluation ═══")
    try:
        r = _pick_record()
        rating_raw = _input("Rating (1-5)",
                                default=str(r.evaluation_rating)
                                if r.evaluation_rating else "")
        notes = _multiline("Evaluation notes",
                              default=r.evaluation_notes or "")
        impact = _multiline("Impact on practice",
                                default=r.impact_on_practice or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rating = (int(rating_raw) if rating_raw
              and rating_raw.isdigit() else None)
    try:
        data.record_evaluation(r.record_id, rating=rating,
                                    notes=notes or None,
                                    impact=impact or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Evaluation recorded on #{r.record_id}")
    _pause()


def records_file_certificate() -> None:
    print("\n═══ File Certificate ═══")
    try:
        r = _pick_record()
        ref = _input("Certificate reference",
                        default=r.certificate_ref or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.file_certificate(r.record_id, ref=ref or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Certificate filed on #{r.record_id}")
    _pause()


def records_set_status() -> None:
    print("\n═══ Change Status ═══")
    try:
        r = _pick_record()
        new_status = _pick_from("New status",
                                  list(RECORD_STATUSES),
                                  default=r.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_record_status(r.record_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{r.record_id} → {new_status}")
    _pause()


def records_delete() -> None:
    print("\n═══ Delete Record ═══")
    try:
        r = _pick_record()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete record #{r.record_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_record(r.record_id):
        print(f"\n  ✓ Deleted #{r.record_id}")
    _pause()


# ── Summary ──────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ CPD Summary ═══")
    s = data.summary()
    print(f"\n  Total activities       : {s.total_activities}")
    print(f"  Upcoming               : {s.upcoming_activities}")
    print(f"  Completed activities   : {s.completed_activities}")
    print(f"  Total records          : {s.total_records}")
    print(f"  Completed records      : {s.completed_records}")
    print(f"  Total hours logged     : {s.total_hours_logged}")
    print(f"  Awaiting certificate   : {s.awaiting_certificate}")
    print(f"  Distinct staff         : {s.distinct_staff}")
    print(f"  Average rating         : "
          f"{s.average_rating if s.average_rating is not None else '—'}")
    print("\n  By activity type:")
    for k in ACTIVITY_TYPES:
        n = s.by_activity_type.get(k, 0)
        if n:
            print(f"    {k:<24}: {n}")
    print("\n  By activity status:")
    for k in ACTIVITY_STATUSES:
        n = s.by_activity_status.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By record status:")
    for k in RECORD_STATUSES:
        n = s.by_record_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("── Activities ──",      lambda: None),
    ("List all",              activities_list),
    ("Upcoming",              activities_upcoming),
    ("Completed",             activities_completed),
    ("Filter",                activities_filter),
    ("New activity",          activities_new),
    ("Edit activity",         activities_edit),
    ("Mark completed",        activities_mark_completed),
    ("Change status",         activities_set_status),
    ("Delete activity",       activities_delete),
    ("── Records ──",         lambda: None),
    ("List all",              records_list),
    ("Awaiting certificate",  records_awaiting_cert),
    ("Completed",             records_completed),
    ("Per-staff",             records_per_staff),
    ("For activity",          records_for_activity),
    ("Filter",                records_filter),
    ("New record",            records_new),
    ("Edit record",           records_edit),
    ("Mark attended",         records_mark_attended),
    ("Record evaluation",     records_evaluate),
    ("File certificate",      records_file_certificate),
    ("Change status",         records_set_status),
    ("Delete record",         records_delete),
    ("──",                    lambda: None),
    ("Summary",               summary_flow),
]


def run() -> None:
    while True:
        print("\n── CPD ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label}")
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
            logger.exception("CPD CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "CPD":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("CPD CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
