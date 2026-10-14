"""CLI flows for Sixth Form Staff HR."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.staff.staff_hr import (
    staff_hr as data,
)
from education_system.systems.sixth_form.domain.staff.staff_hr.staff_hr import (
    CONTRACT_TYPES,
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_EMPLOYMENT_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_EVENT_TYPE,
    DEFAULT_SALARY_SCALE,
    EMPLOYMENT_STATUSES,
    EVENT_STATUSES,
    EVENT_TYPES,
    HREvent,
    HRRecord,
    SALARY_SCALES,
    ValidationError,
)
from education_system.systems.sixth_form.domain.staff import (
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
        print(f"    {i:>3}) {s.staff_id:<12}  {full}  "
              f"({getattr(s, 'role', '—')})")
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


def _pick_record() -> HRRecord:
    rows = data.list_records()
    if not rows:
        print("    No HR records yet.")
        raise _UserAbort
    print("\n  HR records:")
    for i, r in enumerate(rows, 1):
        flag = ""
        if r.dbs_expired:
            flag += "!"
        if r.review_overdue:
            flag += "R"
        print(f"    {i:>3}){flag:<2} #{r.record_id}  "
              f"{r.staff_id:<12}  "
              f"{r.employment_status[:12]:<12}  "
              f"{r.contract_type[:12]:<12}  "
              f"FTE {r.fte_percent}")
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


def _pick_event() -> HREvent:
    rows = data.list_events()
    if not rows:
        print("    No events yet.")
        raise _UserAbort
    print("\n  Events:")
    for i, e in enumerate(rows, 1):
        print(f"    {i:>3}) #{e.event_id}  {e.staff_id:<12}  "
              f"{e.event_type[:16]:<16}  "
              f"{e.start_date} → {e.end_date or '—'}  "
              f"[{e.event_status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((e for e in rows
                            if e.event_id == n), None)
            if match:
                return match
        print("    No matching event.")


# ── Record print ────────────────────────────────────────────

def _print_records(rows: list[HRRecord]) -> None:
    if not rows:
        print("\n  (no records)")
        return
    print()
    print(f"  {'#':>4}  {'Staff':<12}  {'Status':<12}  "
          f"{'Contract':<14}  FTE  Scale  "
          f"DBS exp.    Sg exp.     Review")
    print("  " + "-" * 120)
    for r in rows:
        flags = []
        if r.dbs_expired:
            flags.append("DBS")
        if r.safeguarding_expired:
            flags.append("SG")
        if r.review_overdue:
            flags.append("REV")
        if r.probation_ending_soon:
            flags.append("PROB-30d")
        print(f"  {r.record_id:>4}  {r.staff_id:<12}  "
              f"{r.employment_status[:12]:<12}  "
              f"{r.contract_type[:14]:<14}  "
              f"{r.fte_percent:>3}  "
              f"{r.salary_scale[:6]:<6}  "
              f"{(r.dbs_expires_on or '—'):<10}  "
              f"{(r.safeguarding_expires_on or '—'):<10}  "
              f"{(r.next_review_due or '—'):<10}  "
              f"{','.join(flags)}")
    print(f"\n  {len(rows)} record(s).")


def _print_record_full(r: HRRecord) -> None:
    print()
    print(f"    #{r.record_id}  Staff {r.staff_id}")
    print(f"    Employment       : {r.employment_status}")
    print(f"    Contract         : {r.contract_type}")
    print(f"    FTE              : {r.fte_percent}%")
    print(f"    Scale / spine    : {r.salary_scale}  "
          f"{r.spine_point or '—'}")
    print(f"    Salary           : "
          f"£{r.salary_amount:.0f}"
          if r.salary_amount else "    Salary           : —")
    print(f"    Holiday entitle. : "
          f"{r.holiday_entitlement_days or '—'} days")
    print(f"    Start date       : {r.start_date}")
    print(f"    Probation end    : {r.probation_end or '—'}"
          + ("  (ending soon)"
              if r.probation_ending_soon else ""))
    print(f"    Contract end     : {r.contract_end or '—'}")
    print(f"    End date         : {r.end_date or '—'}")
    print(f"    DBS              : "
          f"{r.dbs_number or '—'}  "
          f"issued {r.dbs_issued_on or '—'}  "
          f"expires {r.dbs_expires_on or '—'}"
          + ("  (EXPIRED)" if r.dbs_expired else ""))
    print(f"    Right to work    : "
          f"{'yes' if r.right_to_work_checked else 'no'}  "
          f"on {r.right_to_work_checked_on or '—'}")
    print(f"    Safeguarding     : "
          f"{r.safeguarding_training_on or '—'} → "
          f"{r.safeguarding_expires_on or '—'}"
          + ("  (EXPIRED)" if r.safeguarding_expired else ""))
    print(f"    Last review      : {r.last_review_on or '—'}")
    print(f"    Next review due  : {r.next_review_due or '—'}"
          + ("  (OVERDUE)" if r.review_overdue else ""))
    print(f"    Pension enrolled : "
          f"{'yes' if r.pension_enrolled else 'no'}")
    print(f"    Union            : {r.union_member or '—'}")
    if r.notes:
        print("\n    Notes:")
        for line in r.notes.splitlines():
            print(f"      {line}")


# ── Record flows ────────────────────────────────────────

def records_list() -> None:
    print("\n═══ All HR Records ═══")
    _print_records(data.list_records())
    _pause()


def records_active() -> None:
    print("\n═══ Active HR Records ═══")
    _print_records(data.list_records(active_only=True))
    _pause()


def records_probation() -> None:
    print("\n═══ On Probation ═══")
    _print_records(data.list_records(probation_only=True))
    _pause()


def records_dbs_expired() -> None:
    print("\n═══ DBS Expired ═══")
    _print_records(data.list_records(dbs_expired=True))
    _pause()


def records_sg_expired() -> None:
    print("\n═══ Safeguarding Expired ═══")
    _print_records(data.list_records(safeguarding_expired=True))
    _pause()


def records_reviews_overdue() -> None:
    print("\n═══ Reviews Overdue ═══")
    _print_records(data.list_records(reviews_overdue=True))
    _pause()


def records_rtw_missing() -> None:
    print("\n═══ Right-to-Work Missing ═══")
    _print_records(data.list_records(rtw_missing=True))
    _pause()


def records_filter() -> None:
    print("\n═══ Filter Records ═══")
    try:
        es = _input(
            f"Employment ({'/'.join(EMPLOYMENT_STATUSES[:3])}…)") or None
        ct = _input(
            f"Contract ({'/'.join(CONTRACT_TYPES[:3])}…)") or None
        scale = _input(
            f"Scale ({'/'.join(SALARY_SCALES[:3])}…)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_records(employment_status=es,
                                  contract_type=ct,
                                  salary_scale=scale)
    _print_records(rows)
    _pause()


def records_view() -> None:
    print("\n═══ View Record ═══")
    try:
        r = _pick_record()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_record_full(r)
    _pause()


def _collect_record_form(
        existing: HRRecord | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["staff_id"] = existing.staff_id
    else:
        payload["staff_id"] = _pick_staff()
    payload["employment_status"] = _pick_from(
        "Employment status", list(EMPLOYMENT_STATUSES),
        default=(existing.employment_status if is_edit
                  else DEFAULT_EMPLOYMENT_STATUS))
    payload["contract_type"] = _pick_from(
        "Contract type", list(CONTRACT_TYPES),
        default=(existing.contract_type if is_edit
                  else DEFAULT_CONTRACT_TYPE))
    payload["fte_percent"] = _input(
        "FTE percent (0-100)",
        default=(str(existing.fte_percent)
                  if is_edit else "100"))
    payload["salary_scale"] = _pick_from(
        "Salary scale", list(SALARY_SCALES),
        default=(existing.salary_scale if is_edit
                  else DEFAULT_SALARY_SCALE))
    payload["spine_point"] = _input(
        "Spine point",
        default=(existing.spine_point or "") if is_edit else "")
    payload["salary_amount"] = _input(
        "Salary (£)",
        default=(str(existing.salary_amount)
                  if is_edit and existing.salary_amount is not None
                  else ""))
    payload["holiday_entitlement_days"] = _input(
        "Holiday entitlement (days)",
        default=(str(existing.holiday_entitlement_days)
                  if is_edit
                  and existing.holiday_entitlement_days is not None
                  else ""))
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["probation_end"] = _input(
        "Probation end (YYYY-MM-DD)",
        default=(existing.probation_end or "")
        if is_edit else "")
    payload["contract_end"] = _input(
        "Contract end (YYYY-MM-DD)",
        default=(existing.contract_end or "")
        if is_edit else "")
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date or "") if is_edit else "")
    payload["dbs_number"] = _input(
        "DBS number",
        default=(existing.dbs_number or "")
        if is_edit else "")
    payload["dbs_issued_on"] = _input(
        "DBS issued on (YYYY-MM-DD)",
        default=(existing.dbs_issued_on or "")
        if is_edit else "")
    payload["dbs_expires_on"] = _input(
        "DBS expires on (YYYY-MM-DD)",
        default=(existing.dbs_expires_on or "")
        if is_edit else "")
    payload["right_to_work_checked"] = _yes_no(
        "Right to work checked?",
        default=(existing.right_to_work_checked
                  if is_edit else False))
    payload["right_to_work_checked_on"] = _input(
        "Checked on (YYYY-MM-DD)",
        default=(existing.right_to_work_checked_on or "")
        if is_edit else "")
    payload["safeguarding_training_on"] = _input(
        "Safeguarding trained on (YYYY-MM-DD)",
        default=(existing.safeguarding_training_on or "")
        if is_edit else "")
    payload["safeguarding_expires_on"] = _input(
        "Safeguarding expires on (YYYY-MM-DD)",
        default=(existing.safeguarding_expires_on or "")
        if is_edit else "")
    payload["last_review_on"] = _input(
        "Last review on (YYYY-MM-DD)",
        default=(existing.last_review_on or "")
        if is_edit else "")
    payload["next_review_due"] = _input(
        "Next review due (YYYY-MM-DD)",
        default=(existing.next_review_due or "")
        if is_edit else "")
    payload["pension_enrolled"] = _yes_no(
        "Pension enrolled?",
        default=(existing.pension_enrolled
                  if is_edit else True))
    payload["union_member"] = _input(
        "Union",
        default=(existing.union_member or "")
        if is_edit else "")
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def records_new() -> None:
    print("\n═══ New HR Record ═══")
    try:
        payload = _collect_record_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_record(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created record #{r.record_id}")
    _pause()


def records_edit() -> None:
    print("\n═══ Edit HR Record ═══")
    try:
        r = _pick_record()
        payload = _collect_record_form(r)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_record(r.record_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{r.record_id}")
    _pause()


def records_renew_dbs() -> None:
    print("\n═══ Renew DBS ═══")
    try:
        r = _pick_record()
        num = _input("DBS number",
                        default=r.dbs_number or "",
                        allow_empty=False)
        issued = _input("Issued on (YYYY-MM-DD)",
                            default=_date.today().isoformat())
        expires = _input("Expires on (YYYY-MM-DD)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.renew_dbs(r.record_id, number=num,
                          issued_on=issued,
                          expires_on=expires or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ DBS renewed on #{r.record_id}")
    _pause()


def records_safeguarding() -> None:
    print("\n═══ Safeguarding Training Complete ═══")
    try:
        r = _pick_record()
        trained = _input("Trained on (YYYY-MM-DD)",
                            default=_date.today().isoformat())
        expires = _input("Expires on (YYYY-MM-DD)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_safeguarding_completed(
            r.record_id, trained_on=trained,
            expires_on=expires or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Safeguarding updated on #{r.record_id}")
    _pause()


def records_review() -> None:
    print("\n═══ Record Review ═══")
    try:
        r = _pick_record()
        when = _input("Reviewed on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
        next_due = _input("Next review due (YYYY-MM-DD)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_review(r.record_id, reviewed_on=when,
                                next_review_due=next_due or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Review recorded on #{r.record_id}")
    _pause()


def records_set_status() -> None:
    print("\n═══ Change Employment Status ═══")
    try:
        r = _pick_record()
        new_status = _pick_from("New status",
                                  list(EMPLOYMENT_STATUSES),
                                  default=r.employment_status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_employment_status(r.record_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{r.record_id} → {new_status}")
    _pause()


def records_mark_left() -> None:
    print("\n═══ Mark Left ═══")
    try:
        r = _pick_record()
        when = _input("End date (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_left(r.record_id, end_date=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{r.record_id} → Left")
    _pause()


def records_delete() -> None:
    print("\n═══ Delete HR Record ═══")
    try:
        r = _pick_record()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete HR record #{r.record_id}? "
              "Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_record(r.record_id):
        print(f"\n  ✓ Deleted #{r.record_id}")
    _pause()


# ── Event flows ─────────────────────────────────────────

def _print_events(rows: list[HREvent]) -> None:
    if not rows:
        print("\n  (no events)")
        return
    print()
    print(f"  {'#':>4}  {'Staff':<12}  {'Type':<18}  "
          f"{'Start':<10}  {'End':<10}  Days  "
          f"{'Status':<12}  Approved by")
    print("  " + "-" * 110)
    for e in rows:
        print(f"  {e.event_id:>4}  {e.staff_id:<12}  "
              f"{e.event_type[:18]:<18}  "
              f"{e.start_date:<10}  "
              f"{(e.end_date or '—'):<10}  "
              f"{(e.days if e.days is not None else '—'):>5}  "
              f"{e.event_status:<12}  "
              f"{e.approved_by or '—'}")
    print(f"\n  {len(rows)} event(s).")


def events_list() -> None:
    print("\n═══ All Events ═══")
    _print_events(data.list_events())
    _pause()


def events_filter() -> None:
    print("\n═══ Filter Events ═══")
    try:
        sid = _input("Staff id") or None
        et = _input(f"Type ({'/'.join(EVENT_TYPES[:3])}…)") or None
        es = _input(
            f"Status ({'/'.join(EVENT_STATUSES[:3])}…)") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_events(staff_id=sid, event_type=et,
                                     event_status=es,
                                     date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_events(rows)
    _pause()


def events_per_staff() -> None:
    print("\n═══ Per-Staff Events ═══")
    try:
        sid = _pick_staff()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_events(data.list_events(staff_id=sid))
    _pause()


def _collect_event_form(
        existing: HREvent | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["staff_id"] = existing.staff_id
    else:
        payload["staff_id"] = _pick_staff()
    payload["event_type"] = _pick_from(
        "Event type", list(EVENT_TYPES),
        default=(existing.event_type if is_edit
                  else DEFAULT_EVENT_TYPE))
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date or "") if is_edit else "")
    payload["days"] = _input(
        "Days",
        default=(str(existing.days)
                  if is_edit and existing.days is not None
                  else ""))
    payload["hours"] = _input(
        "Hours",
        default=(str(existing.hours)
                  if is_edit and existing.hours is not None
                  else ""))
    payload["reason"] = _input(
        "Reason",
        default=(existing.reason or "") if is_edit else "")
    payload["approved_by"] = _input(
        "Approved by",
        default=(existing.approved_by or "")
        if is_edit else "")
    payload["approved_on"] = _input(
        "Approved on (YYYY-MM-DD)",
        default=(existing.approved_on or "")
        if is_edit else "")
    payload["event_status"] = _pick_from(
        "Status", list(EVENT_STATUSES),
        default=(existing.event_status if is_edit
                  else DEFAULT_EVENT_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def events_new() -> None:
    print("\n═══ New Event ═══")
    try:
        payload = _collect_event_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        e = data.create_event(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created event #{e.event_id}")
    _pause()


def events_edit() -> None:
    print("\n═══ Edit Event ═══")
    try:
        e = _pick_event()
        payload = _collect_event_form(e)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_event(e.event_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{e.event_id}")
    _pause()


def events_approve() -> None:
    print("\n═══ Approve Event ═══")
    try:
        e = _pick_event()
        by = _input("Approved by",
                       default=e.approved_by or "",
                       allow_empty=False)
        when = _input("Approved on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.approve_event(e.event_id, approved_by=by,
                              approved_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.event_id} → Approved")
    _pause()


def events_decline() -> None:
    print("\n═══ Decline Event ═══")
    try:
        e = _pick_event()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.decline_event(e.event_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.event_id} → Declined")
    _pause()


def events_mark_taken() -> None:
    print("\n═══ Mark Taken ═══")
    try:
        e = _pick_event()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_taken(e.event_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.event_id} → Taken")
    _pause()


def events_delete() -> None:
    print("\n═══ Delete Event ═══")
    try:
        e = _pick_event()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete event #{e.event_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_event(e.event_id):
        print(f"\n  ✓ Deleted #{e.event_id}")
    _pause()


# ── Summary ─────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Staff HR Summary ═══")
    s = data.summary()
    print(f"\n  Total records           : {s.total_records}")
    print(f"  Active records          : {s.active_records}")
    print(f"  On probation            : {s.on_probation}")
    print(f"  Probation ending soon   : {s.probation_ending_soon}")
    print(f"  DBS expired             : {s.dbs_expired}")
    print(f"  Safeguarding expired    : {s.safeguarding_expired}")
    print(f"  Reviews overdue         : {s.reviews_overdue}")
    print(f"  Right-to-work missing   : {s.right_to_work_missing}")
    print(f"  Total events            : {s.total_events}")
    print(f"  Sick events open        : {s.sick_events_open}")
    print(f"  Annual leave taken days : {s.annual_leave_taken_days}")
    print(f"  Sick days taken         : {s.sick_taken_days}")
    print("\n  By employment status:")
    for k in EMPLOYMENT_STATUSES:
        n = s.by_employment_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By contract type:")
    for k in CONTRACT_TYPES:
        n = s.by_contract_type.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By scale:")
    for k in SALARY_SCALES:
        n = s.by_scale.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By event type:")
    for k in EVENT_TYPES:
        n = s.by_event_type.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("── Records ──",        lambda: None),
    ("List all",             records_list),
    ("Active only",          records_active),
    ("On probation",         records_probation),
    ("DBS expired",          records_dbs_expired),
    ("Safeguarding expired", records_sg_expired),
    ("Reviews overdue",      records_reviews_overdue),
    ("Right-to-work missing", records_rtw_missing),
    ("Filter",               records_filter),
    ("View",                 records_view),
    ("New record",           records_new),
    ("Edit record",          records_edit),
    ("Renew DBS",            records_renew_dbs),
    ("Safeguarding done",    records_safeguarding),
    ("Record review",        records_review),
    ("Change status",        records_set_status),
    ("Mark Left",            records_mark_left),
    ("Delete record",        records_delete),
    ("── Events ──",         lambda: None),
    ("List all",             events_list),
    ("Filter",               events_filter),
    ("Per-staff",            events_per_staff),
    ("New event",            events_new),
    ("Edit event",           events_edit),
    ("Approve",              events_approve),
    ("Decline",              events_decline),
    ("Mark taken",           events_mark_taken),
    ("Delete event",         events_delete),
    ("──",                   lambda: None),
    ("Summary",              summary_flow),
]


def run() -> None:
    while True:
        print("\n── Staff HR ──")
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
            logger.exception("Staff HR CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Staff HR":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Staff HR CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
