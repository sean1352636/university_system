"""CLI: feeder-school references — request → sent → chased → received.

The "contact the DSL" flag is yes/no only; no safeguarding or SEND
detail is ever typed in here.
"""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions import (
    admissions_comms as comms,
    references as refs,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _input,
    _pause,
    _pick_applicant,
    _pick_from,
    _run_submenu,
    _UserAbort,
    _yes,
    _attempt,
    _show_messages,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.entry_requirements_cli import (
    _user,
)


def _line(r: refs.Reference) -> str:
    return (f"#{r.reference_id:<4} {r.applicant_id:<10} {r.referee_name[:22]:<22}"
            f" {(r.referee_school or '')[:20]:<20} {r.status:<9} due "
            f"{r.effective_due or '—'}{' OVERDUE' if r.is_overdue else ''}"
            f"{' chases=' + str(r.chase_count) if r.chase_count else ''}"
            f"{' [DSL contact]' if r.contact_dsl else ''}")


def _pick(rows=None) -> refs.Reference:
    rows = rows if rows is not None else refs.list_references()
    if not rows:
        print("    No references.")
        raise _UserAbort
    label = _pick_from("Reference", [_line(r) for r in rows])
    return refs.get_reference(int(label.split()[0].lstrip("#")))


def _try(fn, *a, **kw):
    try:
        out = fn(*a, **kw)
        print("  ✓ Saved")
        return out
    except ValueError as e:
        print(f"  ✗ {e}")
        return None


def list_flow() -> None:
    s = refs.summary()
    print("\n═══ References ═══  " + ", ".join(f"{k} {v}" for k, v in
                                               s.items()))
    st = _pick_from("Show", ["Open", "Overdue", "All"] + list(refs.STATUSES),
                    default="Open")
    rows = refs.list_references(
        open_only=st == "Open", overdue_only=st == "Overdue",
        status=st if st in refs.STATUSES else None)
    for r in rows:
        print("  " + _line(r))
    _pause()


def request_flow() -> None:
    a = _pick_applicant()
    _try(refs.request_reference, a.applicant_id,
         referee_name=_input("Referee name", default=a.reference_name or "",
                             allow_empty=False),
         referee_role=_input("Role (e.g. Head of Year 11)") or None,
         referee_school=_input("School",
                               default=a.previous_school or "") or None,
         referee_email=_input("Email",
                              default=a.reference_contact or "") or None,
         referee_phone=_input("Phone") or None,
         due_date=_input("Due date (blank = 14 days)") or None,
         requested_by=_user(),
         notes=_input("Notes") or None,
         send=_yes("E-mail the request to the referee now?", default="y"))
    _pause()


def _show_letter(subject: str, body: str) -> None:
    print(f"\n  Subject: {subject}\n\n{body}")


def sent_flow() -> None:
    r = _pick(refs.list_references(status="Requested"))
    _show_letter(*refs.render_request(r.reference_id))
    how = _pick_from("Send", ["E-mail it now (outbox)",
                              "Already sent another way — just mark sent",
                              "Not now"], default="E-mail it now (outbox)")
    if how.startswith("E-mail"):
        ok, m = _attempt(comms.send_reference_request, r.reference_id)
        if ok:
            _show_messages([m])
    elif how.startswith("Already"):
        _try(refs.mark_sent, r.reference_id,
             due_date=_input("Due date (blank = keep)") or None)
    _pause()


def chase_flow() -> None:
    due = refs.chase_list()
    print(f"\n  {len(due)} reference(s) due a chase")
    r = _pick(due or refs.list_references(open_only=True))
    _show_letter(*refs.render_chase(r.reference_id))
    how = _pick_from("Chase", ["E-mail the reminder now (outbox)",
                               "Chased another way — just record it",
                               "Not now"],
                     default="E-mail the reminder now (outbox)")
    if how.startswith("E-mail"):
        ok, m = _attempt(comms.send_reference_chase, r.reference_id)
        if ok:
            _show_messages([m])
    elif how.startswith("Chased"):
        _try(refs.chase, r.reference_id)
    _pause()


def edit_referee_flow() -> None:
    r = _pick()
    _try(refs.update_referee, r.reference_id,
         referee_name=_input("Name", default=r.referee_name),
         referee_role=_input("Role", default=r.referee_role or "") or None,
         referee_school=_input("School", default=r.referee_school or "")
         or None,
         referee_email=_input("E-mail", default=r.referee_email or "") or None,
         referee_phone=_input("Phone", default=r.referee_phone or "") or None,
         due_date=_input("Due date", default=r.due_date or "") or None)
    _pause()


def received_flow() -> None:
    r = _pick(refs.list_references(open_only=True))
    print("  Safeguarding / SEND: record ONLY whether the referee asked the "
          "DSL to contact them — no details here.")
    _try(refs.record_received, r.reference_id,
         received_on=_input("Received on (blank = today)") or None,
         attendance_pct=_input("Attendance %") or None,
         predicted_gcses=_input("Predicted GCSEs (e.g. Maths 7, English 6)")
         or None,
         behaviour=_pick_from("Behaviour", ["(none)"]
                              + list(refs.BEHAVIOUR_RATINGS),
                              default="(none)").replace("(none)", "") or None,
         behaviour_comment=_input("Behaviour comment") or None,
         academic_comment=_input("Academic comment") or None,
         contact_dsl=_yes("Referee asks the DSL to contact the school?"),
         recorded_by=_user())
    _pause()


def decline_flow() -> None:
    r = _pick(refs.list_references(open_only=True))
    _try(refs.decline, r.reference_id, notes=_input("Notes") or None)
    _pause()


def cancel_flow() -> None:
    r = _pick(refs.list_references(open_only=True))
    if _yes("Cancel this request?"):
        _try(refs.cancel, r.reference_id)
    _pause()


def adopt_flow() -> None:
    a = _pick_applicant()
    _try(refs.adopt_legacy_reference, a.applicant_id)
    _pause()


def dsl_flow() -> None:
    ids = refs.dsl_flagged_applicants()
    print("\n  Applicants whose referee asked for DSL contact: "
          + (", ".join(ids) or "none"))
    _pause()


MENU = [
    ("List references", list_flow),
    ("Request a reference", request_flow),
    ("Start workflow from applicant's referee fields", adopt_flow),
    ("Send request (shows letter; e-mail or mark sent)", sent_flow),
    ("Chase (shows letter; e-mail or record)", chase_flow),
    ("Record reference received", received_flow),
    ("Referee declined", decline_flow),
    ("Cancel request", cancel_flow),
    ("DSL contact requested — applicants", dsl_flow),
    ("Edit referee details / due date", edit_referee_flow),
]


def run() -> None:
    _run_submenu("Feeder-school References", MENU)
