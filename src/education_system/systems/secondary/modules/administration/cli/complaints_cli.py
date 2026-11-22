"""Complaints in the terminal.

The old menu keeps its numbering: 1 List all, 2 List open, 3 Overdue
responses, 4 Stage 2 / Appeal, 5 Filter, 6 View, (7 separator), 8 New
complaint, 9 Edit complaint, 10 Acknowledge, 11 Start investigation, 12 Issue
response, 13 Escalate, 14 Record satisfaction, 15 Close, 16 Change status,
17 Delete, (18 separator), 19 Summary. New: 20 Timeline / events, 21 Add
event, 22 Governors' panel, 23 Withdraw, 24 Send letter, 25 Unreasonable flag,
26 Serial complainants, 27 Annual report, 28 History, 29 Export CSV. Rules
live in :mod:`modules.administration.domain.complaints`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.administration.domain import complaints as CM
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (CM.ValidationError, CM.PermissionDenied, CM.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick
_ask = prompts.ask


def _table(rows: list[CM.Complaint]) -> None:
    if not rows:
        print("  (no complaints)")
        return
    print(f"  {'ID':<5} {'Received':<10} {'Complainant':<20} {'Category':<20} "
          f"{'Subject':<26} {'Stage':<26} {'Sev':<3} {'Status':<20} Target")
    print("  " + "-" * 140)
    for c in rows:
        print(f"  {c.complaint_id:<5} {c.received_on:<10} {c.complainant_name[:20]:<20} "
              f"{c.category[:20]:<20} {c.subject[:26]:<26} {c.stage[:26]:<26} "
              f"{c.severity:<3} {c.status[:20]:<20} {c.target_response_date or '-'}"
              + ("  (OVERDUE)" if c.overdue else "")
              + ("  [unreasonable]" if c.unreasonable else ""))
    print(f"\n  {len(rows)} complaint(s)")


def _pick_id(p: Principal) -> CM.Complaint | None:
    cid = _int("  Complaint ID: ")
    if cid is None:
        print("  Cancelled.")
        return None
    c = CM.get(cid)
    if not CM.can_see(p, c):
        raise CM.PermissionDenied("You can't see that complaint.")
    return c


# ── Old options 1-6 ──────────────────────────────────────────────────

def _list_all(p: Principal) -> None:
    _table(CM.list_complaints(actor=p))


def _list_open(p: Principal) -> None:
    _table(CM.list_complaints(actor=p, open_only=True))


def _list_overdue(p: Principal) -> None:
    rows = CM.overdue(actor=p)
    if not rows:
        print("  Nothing overdue.")
        return
    for c, what, due in rows:
        print(f"  #{c.complaint_id:<5} {c.complainant_name[:22]:<22} {c.subject[:30]:<30} "
              f"{what:<34} due {due}")


def _list_stage_2(p: Principal) -> None:
    _table(CM.list_complaints(actor=p, stage2_or_higher=True))


def _filter(p: Principal) -> None:
    f: dict[str, Any] = {}
    for key, label, options in (("category", "Category", CM.CATEGORIES),
                                ("stage", "Stage", CM.STAGES),
                                ("status", "Status", CM.STATUSES),
                                ("outcome", "Outcome", CM.OUTCOMES),
                                ("complainant_role", "Complainant role",
                                 CM.COMPLAINANT_ROLES)):
        v = _pick(label + " (blank = any)", options)
        if v:
            f[key] = v
    for key, label in (("subject_like", "Subject contains"),
                       ("complainant_like", "Complainant contains"),
                       ("assigned_to_like", "Assigned to contains"),
                       ("date_from", "Received from (YYYY-MM-DD)"),
                       ("date_to", "Received to (YYYY-MM-DD)")):
        v = _ask(label)
        if v:
            f[key] = v
    sev = _int("  Minimum severity (1-5, blank = any): ")
    if sev:
        f["severity_min"] = sev
    f["open_only"] = _yes("  Open only?")
    _table(CM.list_complaints(actor=p, **f))


def _view(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    print(f"\n  Complaint #{c.complaint_id} - {c.subject}")
    for label, v in (("Received", c.received_on),
                     ("Complainant", f"{c.complainant_name} ({c.complainant_role})"),
                     ("E-mail", c.contact_email), ("Phone", c.contact_phone),
                     ("Address", c.complainant_address), ("Pupil", c.pupil_name),
                     ("Category", c.category), ("Stage", c.stage),
                     ("Severity", f"{c.severity} {c.severity_label}"),
                     ("Assigned to", c.assigned_to), ("Acknowledge by", c.ack_due),
                     ("Acknowledged", c.acknowledged_on),
                     ("Respond by", c.target_response_date),
                     ("Responded", c.response_issued_on), ("Outcome", c.outcome),
                     ("Satisfaction", c.complainant_satisfaction), ("Status", c.status),
                     ("Closed", c.closed_on), ("Panel", " ".join(
                         x for x in (c.panel_date, c.panel_members) if x)),
                     ("Linked to", c.linked_to), ("Description", c.description),
                     ("Response", c.response_summary), ("Actions", c.actions_taken),
                     ("Notes", c.notes)):
        if v:
            print(f"  {label + ':':<16} {v}")
    flags = [n for n, on in (("complainant informed", c.complainant_informed),
                             ("escalated to stage 2", c.escalated_to_stage_2),
                             ("escalated to appeal", c.escalated_to_appeal),
                             ("governors informed", c.governors_informed),
                             ("UNREASONABLE complainant", c.unreasonable)) if on]
    if flags:
        print(f"  {'Flags:':<16} {', '.join(flags)}")
    if c.overdue:
        print("  ! Overdue")


# ── Old options 8-17 ─────────────────────────────────────────────────

def _details(cur: CM.Complaint | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}

    def g(k: str) -> Any:
        return getattr(cur, k) if cur else None
    for key, label, required in (("subject", "Subject", True),
                                 ("complainant_name", "Complainant name", True)):
        v = _ask(label, g(key), required=required and cur is None)
        if v is not None:
            out[key] = v
    role = _pick("Complainant role", CM.COMPLAINANT_ROLES,
                 g("complainant_role") or CM.DEFAULT_COMPLAINANT_ROLE)
    if role:
        out["complainant_role"] = role
    for key, label in (("contact_email", "Contact e-mail"), ("contact_phone", "Contact phone"),
                       ("complainant_address", "Address"),
                       ("received_on", "Received on (blank = today)")):
        v = _ask(label, g(key))
        if v is not None:
            out[key] = v
    cat = _pick("Category", CM.CATEGORIES, g("category") or CM.DEFAULT_CATEGORY)
    if cat:
        out["category"] = cat
    if cur is None:
        st = _pick("Stage", CM.STAGES, CM.DEFAULT_STAGE)
        if st:
            out["stage"] = st
    for key, label in (("severity", "Severity (1-5)"), ("assigned_to", "Assigned to"),
                       ("acknowledged_on", "Acknowledged on"),
                       ("target_response_date", "Target response date (blank = by stage)"),
                       ("response_issued_on", "Response issued on"),
                       ("description", "Description"), ("response_summary", "Response summary"),
                       ("actions_taken", "Actions taken")):
        v = _ask(label, g(key))
        if v is not None:
            out[key] = v
    oc = _pick("Outcome (blank = none yet)", CM.OUTCOMES, g("outcome"))
    if oc:
        out["outcome"] = oc
    for key, label in (("linked_to", "Linked to"), ("closed_on", "Closed on"),
                       ("notes", "Notes")):
        v = _ask(label, g(key))
        if v is not None:
            out[key] = v
    pupil = _ask("Linked pupil (ID / admission no.)",
                 str(cur.pupil_id) if cur and cur.pupil_id else None)
    if pupil is not None:
        out["pupil_id"] = pupil
    if cur is not None:
        for flag, label in (("complainant_informed", "Complainant informed"),
                            ("governors_informed", "Governors informed")):
            v = _ask(label + " (y/n)", "y" if getattr(cur, flag) else "n")
            if v is not None:
                out[flag] = v.lower().startswith("y")
    return out


def _warn_ok(p: Principal, data: dict[str, Any], cid: int | None = None) -> bool:
    warnings = CM.check(data, actor=p, complaint_id=cid)
    for w in warnings:
        print(f"  ! {w}")
    return not warnings or _yes("  Save anyway?")


def _new(p: Principal) -> None:
    data = _details()
    if not _warn_ok(p, data):
        print("  Not saved.")
        return
    c = CM.create_complaint(data, actor=p)
    print(f"\n  Complaint #{c.complaint_id} saved ({c.stage}). Acknowledge by {c.ack_due}, "
          f"respond by {c.target_response_date}.")


def _edit(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    data = _details(c)
    if not data:
        print("  Nothing changed.")
        return
    if not _warn_ok(p, data, c.complaint_id):
        print("  Not saved.")
        return
    CM.update_complaint(c.complaint_id, data, actor=p)
    print("  Saved.")


def _offer_letter(p: Principal, c: CM.Complaint, kind: str) -> None:
    if c.contact_email and _yes(f"  E-mail the {kind} letter to {c.contact_email}?"):
        _send(p, c.complaint_id, kind, None)


def _acknowledge(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    assigned = _ask("Assign to", c.assigned_to) if CM.is_editor(p) else None
    day = _ask("Acknowledged on (blank = today)")
    target = _ask("Target response date", c.target_response_date)
    c = CM.acknowledge(c.complaint_id, actor=p, assigned_to=assigned, acknowledged_on=day,
                       target_response_date=target)
    print(f"  Acknowledged. Respond by {c.target_response_date}.")
    _offer_letter(p, c, "acknowledgement")


def _investigate(p: Principal) -> None:
    c = _pick_id(p)
    if c is not None:
        CM.start_investigation(c.complaint_id, actor=p)
        print("  Under investigation.")


def _respond(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    outcome = _pick("Outcome", CM.OUTCOMES) or ""
    summary = _ask("Response summary", required=True) or ""
    actions = _ask("Actions taken") or ""
    day = _ask("Issued on (blank = today)")
    c = CM.issue_response(c.complaint_id, actor=p, summary=summary, outcome=outcome,
                          issued_on=day, actions_taken=actions)
    print("  Response issued.")
    _offer_letter(p, c, "response")


def _escalate(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    later = list(CM.STAGES[c.stage_no:])
    if not later:
        print("  The complaint is at the last stage.")
        return
    print(f"  Now at {c.stage}.")
    for w in CM.escalation_problems(c, later[0]):
        print(f"  ! {w}")
    to = _pick("Escalate to", later, later[0]) or later[0]
    reason = _ask("Reason") or ""
    day = _ask("Requested on (blank = today)")
    c = CM.escalate(c.complaint_id, actor=p, to_stage=to, reason=reason, requested_on=day)
    print(f"  Escalated to {c.stage}. Respond by {c.target_response_date}.")
    _offer_letter(p, c, "escalation")


def _satisfaction(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    s = _pick("Satisfaction", CM.SATISFACTIONS, c.complainant_satisfaction)
    if s:
        CM.record_satisfaction(c.complaint_id, actor=p, satisfaction=s)
        print("  Recorded.")


def _close(p: Principal) -> None:
    c = _pick_id(p)
    if c is not None:
        c = CM.close_complaint(c.complaint_id, actor=p,
                               closed_on=_ask("Closed on (blank = today)"))
        print(f"  Closed {c.closed_on}.")


def _status(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    s = _pick("Status", CM.STATUSES, c.status)
    if s:
        CM.set_status(c.complaint_id, s, actor=p)
        print("  Saved.")


def _delete(p: Principal) -> None:
    c = _pick_id(p)
    if c is not None and _yes(f"  Delete complaint #{c.complaint_id} ({c.subject})?"):
        CM.delete_complaint(c.complaint_id, actor=p)
        print("  Deleted.")


def _summary(p: Principal) -> None:
    if not CM.is_editor(p):
        print("  The summary is for the complaints lead.")
        return
    s = CM.summary()
    print(f"\n  Total {s.total}   Open {s.open_count}   Overdue {s.overdue}   "
          f"Closed {s.closed_count}")
    print(f"  Serious or major {s.serious_or_major}   Stage 2 or above "
          f"{s.at_stage_2_or_appeal}   Governors informed {s.governors_informed}")
    print(f"  Upheld {s.upheld_count}   Not upheld {s.not_upheld_count}   Unreasonable "
          f"{s.unreasonable}   Average days to close "
          + ("-" if s.average_days_to_close is None else str(s.average_days_to_close)))
    for title, d in (("By category", s.by_category), ("By stage", s.by_stage),
                     ("By status", s.by_status), ("By outcome", s.by_outcome)):
        print(f"\n  {title}:")
        for k, v in d.items():
            print(f"    {k:<30} {v}")


# ── New options 20-29 ────────────────────────────────────────────────

def _timeline(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    events = CM.list_events(c.complaint_id)
    if not events:
        print("  No events.")
    for e in events:
        print(f"  [{e.event_id}] {e.event_date}  {e.event_type:<16} {e.summary}"
              + (f"  ({e.created_by})" if e.created_by else ""))
    if events and CM.is_editor(p) and _yes("  Delete an event?"):
        eid = _int("  Event ID: ")
        if eid:
            CM.delete_event(eid, actor=p)
            print("  Deleted.")


def _add_event(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    data = {"event_type": _pick("Type", CM.EVENT_TYPES, "Note"),
            "event_date": _ask("Date (blank = today)"),
            "summary": _ask("Summary", required=True)}
    CM.add_event(c.complaint_id, data, actor=p)
    print("  Added.")


def _panel(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    day = _ask("Panel date", c.panel_date, required=True) or c.panel_date or ""
    members = _ask("Members (comma-separated, at least 3)", c.panel_members,
                   required=True) or c.panel_members or ""
    CM.set_panel(c.complaint_id, actor=p, panel_date=day, members=members,
                 note=_ask("Note"))
    print("  Panel recorded.")


def _withdraw(p: Principal) -> None:
    c = _pick_id(p)
    if c is not None and _yes(f"  Withdraw complaint #{c.complaint_id}?"):
        CM.withdraw(c.complaint_id, actor=p, reason=_ask("Why (optional)") or "")
        print("  Withdrawn and closed.")


def _send(p: Principal, cid: int, kind: str, note: str | None) -> None:
    res = CM.send_letter(cid, kind, actor=p, note=note)
    if not res["message_id"]:
        print("  No e-mail address - post the letter and add an event.")
        return
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    try:
        E.deliver(res["message_id"], principal=p)
        print("  Sent.")
    except Exception as e:  # delivery failure leaves it queued in the outbox
        print(f"  Queued in the outbox - delivery failed: {e}")


def _letter(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    kind = _pick("Letter", list(CM.LETTERS), "acknowledgement")
    if kind:
        _send(p, c.complaint_id, kind, _ask("Extra paragraph (optional)"))


def _unreasonable(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    print(f"  {c.complainant_name} is {'' if c.unreasonable else 'not '}flagged.")
    flag = _yes("  Flag as unreasonable / serial (n clears it)?")
    notes = _ask("Why, and the communication plan", c.unreasonable_notes) if flag else None
    review = _ask("Review on (blank = 6 months)", c.unreasonable_review) if flag else None
    CM.flag_unreasonable(c.complaint_id, flag, actor=p, notes=notes, review_date=review)
    print("  Saved for all of this complainant's complaints.")


def _serial(p: Principal) -> None:
    if not CM.is_editor(p):
        print("  For the complaints lead.")
        return
    rows = CM.serial_complainants()
    if not rows:
        print("  None.")
    for x in rows:
        print(f"  {x['complainant'][:26]:<26} {(x['email'] or '')[:28]:<28} {x['count']:>3}"
              f"  {'FLAGGED' if x['flagged'] else '':<8} "
              + ", ".join(f"#{i}" for i in x["ids"]))


def _annual(p: Principal) -> None:
    if not CM.is_editor(p):
        print("  For the complaints lead.")
        return
    r = CM.annual_report(_ask("School year", CM.current_year()))
    print(f"\n  Complaints report - {r['academic_year']}")
    print(f"  Received {r['received']}   Closed {r['closed']}   Open {r['open']}   "
          f"Withdrawn {r['withdrawn']}   Panels {r['panels']}")
    print(f"  Responses on time {r['responses_on_time']} of {r['responses']}"
          + (f" ({r['on_time_pct']}%)" if r["on_time_pct"] is not None else ""))
    for title, key in (("By category", "by_category"), ("Stage reached", "by_stage_reached"),
                       ("By outcome", "by_outcome"), ("By complainant", "by_role")):
        print(f"\n  {title}:")
        for k, v in r[key].items():
            print(f"    {k:<32} {v}")


def _history(p: Principal) -> None:
    c = _pick_id(p)
    if c is None:
        return
    rows = CM.history(c.complaint_id)
    if not rows:
        print("  No changes recorded.")
    for h in rows:
        print(f"  {h['at']}  {h['actor']:<14} {h['action']:<12} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(p: Principal) -> None:
    path = _ask("Save CSV to", "complaints.csv") or "complaints.csv"
    n = CM.export_csv(path, actor=p, open_only=_yes("  Open complaints only?"))
    print(f"  Exported {n} complaint(s) to {path}.")


def _separator(_p: Principal) -> None:
    return None


_OPTIONS = {"1": _list_all, "2": _list_open, "3": _list_overdue, "4": _list_stage_2,
            "5": _filter, "6": _view, "7": _separator, "8": _new, "9": _edit,
            "10": _acknowledge, "11": _investigate, "12": _respond, "13": _escalate,
            "14": _satisfaction, "15": _close, "16": _status, "17": _delete,
            "18": _separator, "19": _summary, "20": _timeline, "21": _add_event,
            "22": _panel, "23": _withdraw, "24": _letter, "25": _unreasonable,
            "26": _serial, "27": _annual, "28": _history, "29": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("complaints.view")
        print("\n  ── Complaints ──")
        print("   1) List all\n   2) List open\n   3) Overdue responses\n   4) Stage 2 / Appeal"
              "\n   5) Filter\n   6) View")
        print("      " + "─" * 18)
        print("   8) New complaint\n   9) Edit complaint\n  10) Acknowledge"
              "\n  11) Start investigation\n  12) Issue response\n  13) Escalate"
              "\n  14) Record satisfaction\n  15) Close\n  16) Change status\n  17) Delete")
        print("      " + "─" * 18)
        print("  19) Summary")
        print("  More")
        print("  20) Timeline / events\n  21) Add event\n  22) Governors' panel\n  23) Withdraw"
              "\n  24) Send letter\n  25) Unreasonable flag\n  26) Serial complainants"
              "\n  27) Annual report\n  28) History\n  29) Export CSV")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        if fn is _separator:
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
