"""Staff absence in the terminal (HR).

The old Staff Absence menu keeps its numbers: 1 List all, 2 Open only,
3 Active today, 4 Critical open, 5 Cover outstanding, 6 Return overdue,
7 RTW overdue, 8 Filter, 9 Per-staff, 10 View, 12 New absence, 13 Edit
absence, 14 Confirm, 15 Arrange cover, 16 Record return, 17 Complete RTW,
18 Close, 19 Cancel, 20 Change status, 21 Delete, 23 Summary (11 and 22
were the separators). New, after "More": 24 Report sickness, 25 Still off,
26 Certificate / fit note, 27 Requests, 28 New request, 29 Approve request,
30 Decline request, 31 Withdraw request, 32 Sickness record (Bradford),
33 Trigger points reached, 34 Trigger settings, 35 Who is off on a date,
36 Month calendar, 37 Reports, 38 Cover lessons, 39 History, 40 Export CSV.
Rules: :mod:`modules.staff.domain.staff_absence`.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import cover as CV
from education_system.systems.secondary.modules.staff.domain import staff_absence as SA
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (SA.ValidationError, SA.PermissionDenied, SA.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _table(rows: list[SA.Record]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print(f"\n  {'Id':<5} {'Date':<10} {'Last':<10} {'Staff':<22} {'Type':<20} "
          f"{'Exp ret':<10} {'Act ret':<10} {'Status':<10} {'Cover':<14} {'Days':>5}  Flags")
    print("  " + "-" * 130)
    for r in rows:
        print(f"  {r.absence_id:<5} {r.start_date:<10} {r.end_date:<10} {r.staff_name[:22]:<22} "
              f"{r.absence_type[:20]:<20} {r.expected_return or '—':<10} "
              f"{r.actual_return or '—':<10} {r.status:<10} {r.cover_source[:14]:<14} "
              f"{r.days:>5g}  {','.join(r.flags)}")
    print(f"\n  {len(rows)} absence(s)")


def _list(principal: Principal, **filters: Any) -> None:
    _table(SA.list_absences(actor=principal, **filters))


def _staff(label: str = "Staff (login or name)") -> dict[str, Any]:
    text = _prompt(f"  {label}: ")
    choices = SA.staff_choices()
    hit = next((p for p in choices if (p["username"] or "").lower() == text.lower()
                or p["name"].lower() == text.lower()), None)
    if hit:
        return {"staff_username": hit["username"], "staff_name": hit["name"]}
    return {"staff_username": None, "staff_name": text or None}


def _record() -> SA.Record | None:
    aid = _int("  Absence id: ")
    return SA.get(aid) if aid else None


def _ask(label: str, cur: Any = None) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _details(cur: SA.Record | None = None) -> dict[str, Any]:
    """The old questions (Enter keeps the current value), then the new ones."""
    out: dict[str, Any] = {}
    for key, label in (("start_date", "Absence date (YYYY-MM-DD)"),
                       ("end_date", "Last day off (blank = from expected return)"),
                       ("expected_return", "Expected return"),
                       ("actual_return", "Actual return")):
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = v
    t = _pick("Absence type", SA.ABSENCE_TYPES,
              cur.absence_type if cur else SA.DEFAULT_ABSENCE_TYPE)
    if t:
        out["absence_type"] = t
    for key, label, options in (
            ("notification_method", "Notification", SA.NOTIFICATION_METHODS),
            ("certificate_type", "Certificate", SA.CERTIFICATE_TYPES),
            ("cover_source", "Cover source", SA.COVER_SOURCES),
            ("status", "Status", SA.STATUSES)):
        v = _pick(label, options, getattr(cur, key) if cur else None)
        if v:
            out[key] = v
    for key, label in (("reason", "Reason (HR only)"), ("notified_on", "Notified on"),
                       ("notified_by", "Notified by"),
                       ("cert_received_on", "Cert received on"),
                       ("cover_arranged_by", "Cover arranged by"),
                       ("rtw_meeting_on", "RTW meeting on"),
                       ("rtw_completed_by", "RTW completed by"),
                       ("days_lost", "Days lost (blank = weekdays)"),
                       ("from_period", "From period (blank = all day)"),
                       ("to_period", "To period"), ("fit_note_from", "Fit note from"),
                       ("fit_note_to", "Fit note to"), ("cover_notes", "Cover notes"),
                       ("rtw_notes", "RTW interview notes"), ("notes", "Notes")):
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = v
    for key, label in (("cover_required", "Cover required"), ("critical", "Critical absence"),
                       ("parents_informed", "Parents informed"),
                       ("slt_informed", "SLT informed"), ("rtw_required", "RTW required"),
                       ("paid", "Paid")):
        v = _ask(f"{label} (y/n)", ("y" if getattr(cur, key) else "n") if cur else "")
        if v:
            out[key] = v.lower() in ("y", "yes")
    return out


# ── The old options ──────────────────────────────────────────────────

def _filter(principal: Principal) -> None:
    f: dict[str, Any] = {}
    staff = _prompt("  Staff (blank = all): ")
    if staff:
        f["staff"] = staff
    for key, label, options in (("absence_type", "Type", SA.ABSENCE_TYPES),
                                ("status", "Status", SA.STATUSES),
                                ("cover_source", "Cover", SA.COVER_SOURCES)):
        v = _pick(f"{label} (blank = any)", options)
        if v:
            f[key] = v
    for key, label in (("date_from", "From (YYYY-MM-DD)"), ("date_to", "To")):
        v = _prompt(f"  {label}: ")
        if v:
            f[key] = v
    _list(principal, **f)


def _per_staff(principal: Principal) -> None:
    who = _staff()
    _list(principal, staff=who["staff_username"] or who["staff_name"] or "")


def _view(principal: Principal) -> None:
    r = _record()
    if r is None:
        return
    r = SA.get_absence(r.absence_id, actor=principal)
    print(f"\n  Absence #{r.absence_id} - {r.staff_name}"
          + (f" ({r.staff_username})" if r.staff_username else ""))
    for label, v in (("Dates", f"{r.dates_label} ({r.periods_label})"),
                     ("Type", r.absence_type), ("Paid", "yes" if r.paid else "no"),
                     ("Status", r.status), ("Reason", r.reason),
                     ("Expected return", r.expected_return), ("Actual return", r.actual_return),
                     ("Days lost", f"{r.days:g}"),
                     ("Notified", " ".join(x for x in (r.notified_on, r.notification_method,
                                                       r.notified_by) if x)),
                     ("Certificate", f"{r.certificate_type} {r.cert_received_on or ''}"),
                     ("Fit note", f"{r.fit_note_from} to {r.fit_note_to}"
                      if r.fit_note_from else None),
                     ("Cover", f"{r.cover_source}, {r.cover_total} lesson(s), "
                               f"{r.cover_pending} unassigned"),
                     ("Cover notes", r.cover_notes),
                     ("RTW", f"{r.rtw_meeting_on} by {r.rtw_completed_by}" if r.rtw_meeting_on
                      else ("due" if r.rtw_required else None)),
                     ("RTW notes", r.rtw_notes), ("Approved by", r.approved_by),
                     ("Flags", ",".join(r.flags)), ("Notes", r.notes)):
        if v not in (None, ""):
            print(f"    {label + ':':<17} {v}")


def _new(principal: Principal) -> None:
    data = {**_staff(), **_details()}
    rec, lessons = SA.create_absence(data, actor=principal)
    print(f"\n  Recorded absence #{rec.absence_id}; {lessons} lesson(s) need cover.")


def _edit(principal: Principal) -> None:
    r = _record()
    if r is None:
        return
    changes = _details(r)
    if not changes:
        print("  Nothing changed.")
        return
    _rec, added, cancelled = SA.update_absence(r.absence_id, changes, actor=principal)
    print(f"  Saved. Cover: {added} added, {cancelled} cancelled.")


def _confirm(principal: Principal) -> None:
    r = _record()
    if r:
        print(f"  Status: {SA.confirm(r.absence_id, actor=principal).status}")


def _arrange(principal: Principal) -> None:
    r = _record()
    if r is None:
        return
    print(f"  {r.cover_total} lesson(s) on the Cover screen, {r.cover_pending} unassigned.")
    src = _pick("Source", SA.COVER_SOURCES, r.cover_source)
    SA.arrange_cover(r.absence_id, source=src or r.cover_source, actor=principal,
                     arranged_by=_prompt("  Arranged by: ") or None,
                     notes=_prompt("  Cover notes: ") or None)
    print("  Saved.")


def _return(principal: Principal) -> None:
    r = _record()
    if r is None:
        return
    rec, added, cancelled = SA.record_return(
        r.absence_id, actor=principal,
        returned_on=_prompt("  Returned on (blank = today): ") or None,
        days_lost=_prompt("  Days lost (blank = auto): ") or None)
    print(f"  Back on {rec.actual_return}. Cover cancelled for {cancelled}, added for {added}."
          + (" A return-to-work interview is due." if rec.rtw_outstanding else ""))


def _rtw(principal: Principal) -> None:
    r = _record()
    if r:
        SA.complete_rtw(r.absence_id, actor=principal,
                        completed_by=_prompt("  Completed by: "),
                        meeting_on=_prompt("  Meeting on (blank = today): ") or None,
                        notes=_prompt("  Interview notes: ") or None)
        print("  Saved.")


def _close(principal: Principal) -> None:
    r = _record()
    if r:
        SA.close(r.absence_id, actor=principal)
        print("  Closed.")


def _cancel(principal: Principal) -> None:
    r = _record()
    if r and _yes(f"  Cancel {r.staff_name}'s absence ({r.dates_label}) and its cover?"):
        SA.cancel(r.absence_id, actor=principal)
        print("  Cancelled.")


def _status(principal: Principal) -> None:
    r = _record()
    if r:
        st = _pick("Status", SA.STATUSES, r.status)
        print(f"  Status: {SA.set_status(r.absence_id, st or r.status, actor=principal).status}")


def _delete(principal: Principal) -> None:
    r = _record()
    if r and _yes(f"  Delete absence #{r.absence_id} (recorded in error)?"):
        print(f"  Deleted with {SA.delete(r.absence_id, actor=principal)} cover request(s).")


def _summary(principal: Principal) -> None:
    s = SA.summary(actor=principal)
    print("\n═══ Staff Absence Summary ═══")
    for label, key in (("Total", "total"), ("Open", "open"), ("Active today", "active_today"),
                       ("Cover outstanding", "cover_outstanding"),
                       ("Critical open", "critical_open"), ("RTW overdue", "rtw_overdue"),
                       ("RTW outstanding", "rtw_outstanding"),
                       ("Return overdue", "return_overdue"),
                       ("Awaiting certificate", "awaiting_cert"),
                       ("Parents pending", "parents_pending"),
                       ("Distinct staff", "distinct_staff"),
                       ("Total days lost", "total_days_lost"),
                       ("Requests waiting", "requests_waiting")):
        print(f"  {label:<21}: {s[key]}")
    for head, key in (("By type", "by_type"), ("By status", "by_status"),
                      ("By cover source", "by_cover_source")):
        print(f"\n  {head}:")
        for k, n in s[key].items():
            print(f"    {k:<26}: {n}")


# ── New ──────────────────────────────────────────────────────────────

def _report_sick(principal: Principal) -> None:
    who = _staff("Who is off sick (blank = me)") if SA.is_editor(principal) else {}
    rec, lessons = SA.report_sickness(
        actor=principal, start_date=_prompt("  First day (blank = today): ") or None,
        expected_return=_prompt("  Expected back (blank = not known): ") or None,
        reason=_prompt("  Reason (HR only, blank ok): ") or None,
        **{k: v for k, v in who.items() if v})
    print(f"  Recorded #{rec.absence_id} ({rec.dates_label}); {lessons} lesson(s) need cover.")


def _extend(principal: Principal) -> None:
    r = _record()
    if r:
        _rec, added, _c = SA.extend(r.absence_id, actor=principal,
                                    expected_return=_prompt("  Expected return: ") or None,
                                    last_day=_prompt("  Or new last day off: ") or None)
        print(f"  Cover added for {added} lesson(s).")


def _certificate(principal: Principal) -> None:
    r = _record()
    if r:
        t = _pick("Certificate", SA.CERTIFICATE_TYPES, "Fit Note")
        SA.record_certificate(r.absence_id, certificate_type=t or "Fit Note", actor=principal,
                              received_on=_prompt("  Received on (blank = today): ") or None,
                              fit_from=_prompt("  Fit note from: ") or None,
                              fit_to=_prompt("  Fit note to: ") or None)
        print("  Saved.")


def _requests(principal: Principal) -> None:
    st = _pick("Status (blank = all)", SA.REQUEST_STATUSES)
    rows = SA.list_requests(actor=principal, status=st or None)
    if not rows:
        print("  (none)")
    for q in rows:
        print(f"  #{q.request_id:<4} {q.staff_name[:20]:<20} {q.absence_type[:18]:<18} "
              f"{q.dates_label:<24} {q.days:>4g}d {'paid' if q.paid else 'unpaid':<6} "
              f"{q.status:<9} {q.decision_note or q.reason or ''}")


def _new_request(principal: Principal) -> None:
    who = _staff("For (blank = me)") if SA.is_editor(principal) else {}
    planned = tuple(t for t in SA.ABSENCE_TYPES if t not in SA.SICKNESS_TYPES)
    data: dict[str, Any] = {k: v for k, v in who.items() if v}
    data["absence_type"] = _pick("Type", planned, "Training / CPD")
    for key, label in (("start_date", "First day"), ("end_date", "Last day (blank = same)"),
                       ("from_period", "From period (blank = all day)"),
                       ("to_period", "To period"), ("reason", "Reason")):
        data[key] = _prompt(f"  {label}: ")
    q = SA.request_absence(data, actor=principal)
    print(f"  Request #{q.request_id} sent.")


def _request_id() -> int | None:
    return _int("  Request id: ")


def _approve(principal: Principal) -> None:
    rid = _request_id()
    if rid:
        _q, rec, lessons = SA.approve_request(rid, actor=principal,
                                              note=_prompt("  Note (blank ok): ") or None)
        print(f"  Approved: absence #{rec.absence_id}; {lessons} lesson(s) need cover.")


def _decline(principal: Principal) -> None:
    rid = _request_id()
    if rid:
        SA.decline_request(rid, actor=principal, note=_prompt("  Why: "))
        print("  Declined.")


def _withdraw(principal: Principal) -> None:
    rid = _request_id()
    if rid and _yes(f"  Withdraw request #{rid}?"):
        SA.withdraw_request(rid, actor=principal)
        print("  Withdrawn.")


def _sickness(principal: Principal) -> None:
    who = _staff()
    rec = SA.sickness_record(who["staff_username"] or who["staff_name"] or "", actor=principal)
    print(f"\n  Rolling 12 months {rec['from']} to {rec['to']}: {rec['episodes']} episode(s), "
          f"{rec['days']:g} day(s), Bradford factor {rec['bradford']:g}")
    print("  Trigger points: " + ("; ".join(rec["triggers"]) or "none reached"))
    _table(rec["absences"])


def _triggers(principal: Principal) -> None:
    rows = SA.sickness_overview(actor=principal, triggered_only=True)
    if not rows:
        print("  Nobody has reached a trigger point.")
    for x in rows:
        print(f"  {x['staff'][:24]:<24} {x['department'][:16]:<16} S={x['episodes']:<3} "
              f"D={x['days']:<5g} B={x['bradford']:<7g} {'; '.join(x['triggers'])}")


def _settings(principal: Principal) -> None:
    st = SA.settings()
    changes = {k: _ask(label, st[k]) for k, label in (
        ("trigger_episodes", "Episodes in 12 months"), ("trigger_days", "Days in 12 months"),
        ("bradford_trigger", "Bradford score"),
        ("rtw_overdue_days", "RTW overdue after (days)"))}
    print("  Saved: " + ", ".join(f"{k}={v}" for k, v in
                                  SA.set_settings(changes, actor=principal).items()))


def _on_date(principal: Principal) -> None:
    day = _prompt("  Date (blank = today): ") or _dt.date.today().isoformat()
    _table(SA.on_date(day, actor=principal))


def _calendar(principal: Principal) -> None:
    text = _prompt("  Month (YYYY-MM, blank = this month): ") or f"{_dt.date.today():%Y-%m}"
    try:
        y, m = (int(x) for x in text.split("-"))
    except ValueError:
        print("  Use YYYY-MM.")
        return
    for d, rows in SA.calendar(y, m, actor=principal).items():
        if rows:
            print(f"  {d} {_dt.date.fromisoformat(d):%a}  "
                  + ", ".join(f"{r.staff_name} ({r.absence_type})" for r in rows))


def _reports(principal: Principal) -> None:
    by = _pick("Group by", SA.REPORT_GROUPS, "type") or "type"
    rows = SA.report(by=by, actor=principal,
                     date_from=_prompt("  From (blank = all): ") or None,
                     date_to=_prompt("  To (blank = all): ") or None)
    print(f"\n  {'Group':<30} {'Absences':>8} {'Days':>7} {'Sick':>7} {'Unpaid':>7} "
          f"{'People':>7}")
    for g in rows:
        print(f"  {g['group'][:30]:<30} {g['absences']:>8} {g['days']:>7g} "
              f"{g['sickness_days']:>7g} {g['unpaid_days']:>7g} {g['people']:>7}")


def _cover(_principal: Principal) -> None:
    r = _record()
    if r:
        rows = CV.list_covers(absence_id=r.absence_id)
        for c in rows:
            print(f"  {c.date} P{c.period:<3} {c.group_code:<10} {c.status:<10} "
                  f"{c.cover_name or 'unassigned'}")
        if not rows:
            print("  No lessons to cover.")


def _history(_principal: Principal) -> None:
    r = _record()
    if r:
        for h in SA.history(r.absence_id):
            print(f"  {h['at']}  {h['actor']:<12} {h['action']:<20} "
                  + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. staff_absence.csv): ")
    if path:
        print(f"  Exported {SA.export_csv(path, actor=principal)} absence(s).")


_OPTIONS = {
    "1": lambda p: _list(p), "2": lambda p: _list(p, open_only=True),
    "3": lambda p: _list(p, active_today=True),
    "4": lambda p: _list(p, critical_only=True, open_only=True),
    "5": lambda p: _list(p, cover_outstanding=True),
    "6": lambda p: _list(p, return_overdue=True), "7": lambda p: _list(p, rtw_overdue=True),
    "8": _filter, "9": _per_staff, "10": _view, "12": _new, "13": _edit, "14": _confirm,
    "15": _arrange, "16": _return, "17": _rtw, "18": _close, "19": _cancel, "20": _status,
    "21": _delete, "23": _summary, "24": _report_sick, "25": _extend, "26": _certificate,
    "27": _requests, "28": _new_request, "29": _approve, "30": _decline, "31": _withdraw,
    "32": _sickness, "33": _triggers, "34": _settings, "35": _on_date, "36": _calendar,
    "37": _reports, "38": _cover, "39": _history, "40": _export}

_MENU = """
   1) List all
   2) Open only
   3) Active today
   4) Critical open
   5) Cover outstanding
   6) Return overdue
   7) RTW overdue
   8) Filter
   9) Per-staff
  10) View
      ──────────────────
  12) New absence
  13) Edit absence
  14) Confirm
  15) Arrange cover
  16) Record return
  17) Complete RTW
  18) Close
  19) Cancel
  20) Change status
  21) Delete
      ──────────────────
  23) Summary
  More
  24) Report sickness           25) Still off (extend)
  26) Certificate / fit note    27) Requests
  28) New request               29) Approve request
  30) Decline request           31) Withdraw request
  32) Sickness record           33) Trigger points reached
  34) Trigger settings          35) Who is off on a date
  36) Month calendar            37) Reports
  38) Cover lessons             39) History
  40) Export CSV
   0) Back"""


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("staff_absence.view", principal=principal)
        print("\n── Staff Absence ──" + _MENU)
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
