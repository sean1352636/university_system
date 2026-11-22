"""Medical in the terminal.

The old First Aid menu keeps its options in place: 1 New incident, 2 List
incidents, 3 View incident, 4 Edit incident, 5 Summary report, 6 Delete
incident. Under "More": the old Emergency & Drills menu (7-14: new, list,
view, edit, set status, close, summary, delete), then 15 Who has what and
what to do, 16 Allergy list (trip / kitchen), 17 Conditions, 18 Add
condition, 19 Edit condition, 20 IHP reviewed, 21 Allergies, 22 Add allergy,
23 Medicines in school, 24 Add medicine, 25 Give a medicine, 26 Medicines
given, 27 Return / dispose medicine, 28 Ask family to replace a medicine,
29 Parents told (incident), 30 RIDDOR reported, 31 E-mail family about an
incident, 32 Due, 33 Summary, 34 History, 35 Export CSV. Rules live in
:mod:`modules.medical.domain.medical`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.medical.domain import medical as M
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (M.ValidationError, M.PermissionDenied, M.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _ask(fields: list[tuple[str, str, Any]], current: Any = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, label, choices in fields:
        cur = getattr(current, key, None) if current is not None else None
        if choices:
            v = _pick(label, tuple(choices), str(cur) if cur not in (None, "") else None)
            if v and v != cur:
                out[key] = v
            continue
        v = prompts.ask(label, None if cur is None else str(cur))
        if v is not None:
            out[key] = v
    return out


def _show(obj: Any, fields: list[tuple[str, str, Any]]) -> None:
    for key, label, _c in fields:
        v = getattr(obj, key)
        if v not in (None, "", False):
            print(f"    {label + ':':<26} {'yes' if v is True else v}")


def _deliver(principal: Principal, res: dict[str, Any]) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    if not res["emails"]:
        print("  No contact with parental responsibility has an e-mail address.")
        return
    print(f"  Saved for {res['emails']} contact(s).")
    try:
        E.deliver(res["message_id"], principal=principal)
        print("  Sent.")
    except Exception as e:  # noqa: BLE001 - it stays in the outbox
        print(f"  Saved in the outbox; not sent yet ({e}).")


# ── The old First Aid menu ───────────────────────────────────────────

_FA = [("incident_date", "Date (blank = today)", None), ("incident_time", "Time (HH:MM)", None),
       ("location", "Location", None), ("injury_type", "Injury type", M.INJURY_TYPES),
       ("severity", "Severity", M.SEVERITIES), ("body_part", "Body part", None),
       ("description", "Description", None), ("treatment", "Treatment", None),
       ("treated_by", "Treated by", None), ("outcome", "Outcome", M.OUTCOMES),
       ("parent_contacted", "Parent contacted (y/n)", None),
       ("parent_contact_time", "Parent contact time", None),
       ("hospital_referral", "Hospital referral (y/n)", None),
       ("accident_book_ref", "Accident book ref", None),
       ("riddor_reportable", "RIDDOR reportable (y/n)", None),
       ("follow_up", "Follow-up", None), ("notes", "Notes", None)]


def _fa_table(rows: list[M.Incident]) -> None:
    if not rows:
        print("  (no incidents)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'Time':<5} {'Person':<26} {'Yr':<3} {'Injury':<20} "
          f"{'Sev':<8} {'Outcome':<24} P H R")
    for i in rows:
        print(f"  {i.incident_id:<4} {i.incident_date:<10} {i.incident_time or '':<5} "
              f"{i.who[:26]:<26} {i.pupil_year or '':<3} {i.injury_type[:20]:<20} "
              f"{i.severity:<8} {i.outcome[:24]:<24} {'Y' if i.parent_contacted else '-'} "
              f"{'Y' if i.hospital_referral else '-'} {'Y' if i.riddor_reportable else '-'}")


def _fa_new(principal: Principal) -> None:
    who = _pick("Person", M.PERSON_TYPES, "Pupil") or "Pupil"
    data: dict[str, Any] = {"person_type": who}
    if who == "Pupil":
        data["pupil_id"] = _prompt("  Pupil ID / admission no.: ")
    else:
        data["person_name"] = _prompt("  Name: ")
    data.update(_ask(_FA))
    for w in M.check_incident(data):
        print(f"  ! {w}")
    i = M.create_incident(data, actor=principal)
    print(f"  Created incident #{i.incident_id}.")


def _fa_list(_principal: Principal) -> None:
    sev = _pick("Severity (blank = all)", M.SEVERITIES)
    _fa_table(M.list_incidents(severity=sev or None, riddor_only=_yes("  RIDDOR only?"),
                               hospital_only=_yes("  Hospital only?"),
                               from_date=_prompt("  From (blank = any): ") or None,
                               to_date=_prompt("  To (blank = any): ") or None))


def _incident() -> M.Incident | None:
    iid = _int("  Incident ID: ")
    return M.get_incident(iid) if iid else None


def _fa_view(_principal: Principal) -> None:
    i = _incident()
    if i:
        print(f"\n  Incident #{i.incident_id} - {i.who}")
        _show(i, _FA + [("parent_contact_how", "Parents told how", None),
                        ("riddor_reported_on", "RIDDOR reported", None),
                        ("riddor_reference", "HSE reference", None)])


def _fa_edit(principal: Principal) -> None:
    i = _incident()
    if i:
        M.update_incident(i.incident_id, _ask(_FA, i), actor=principal)
        print("  Saved.")


def _fa_summary(_principal: Principal) -> None:
    s = M.first_aid_summary(from_date=_prompt("  From (blank = any): ") or None,
                            to_date=_prompt("  To (blank = any): ") or None)
    print(f"\n  Total: {s['total']}   Pupils: {s['pupils']}   Parents contacted: "
          f"{s['parent_contacted']}   Hospital: {s['hospital']}   RIDDOR: {s['riddor']} "
          f"({s['riddor_outstanding']} to report)")
    for key in ("by_severity", "by_injury", "by_outcome", "by_location", "by_month"):
        print(f"  {key[3:].title()}: " + ", ".join(f"{k} {v}" for k, v in s[key].items()))


def _fa_delete(principal: Principal) -> None:
    i = _incident()
    if i and _yes(f"  Delete incident #{i.incident_id}?"):
        M.delete_incident(i.incident_id, actor=principal, reason=_prompt("  Why: "))
        print("  Deleted.")


# ── The old Emergency & Drills menu ──────────────────────────────────

_EM = [("kind", "Kind", M.EVENT_KINDS), ("event_type", "Type", M.EMERGENCY_TYPES),
       ("event_date", "Date (blank = today)", None), ("start_time", "Start (HH:MM)", None),
       ("end_time", "End (HH:MM)", None), ("duration_min", "Duration (min, blank = auto)", None),
       ("location", "Location", None), ("trigger", "Trigger", None),
       ("reported_by", "Reported by", None), ("incident_commander", "Incident commander", None),
       ("pupils_evacuated", "Pupils evacuated", None),
       ("staff_evacuated", "Staff evacuated", None), ("missing_count", "Missing", None),
       ("injuries_count", "Injuries", None),
       ("emergency_services", "Emergency services (y/n)", None),
       ("services_attended", "Services attended", None),
       ("outcome", "Outcome", M.EVENT_OUTCOMES), ("status", "Status", M.EVENT_STATUSES),
       ("lessons_learned", "Lessons learned", None),
       ("follow_up_actions", "Follow-up actions", None), ("notes", "Notes", None)]


def _em_table(rows: list[M.Emergency]) -> None:
    if not rows:
        print("  (no events)")
    for e in rows:
        print(f"  #{e.event_id:<4} {e.event_date} {e.kind:<11} {e.event_type[:16]:<16} "
              f"{e.duration_min if e.duration_min is not None else '-':>4} min  pupils "
              f"{e.pupils_evacuated or '-':<5} missing {e.missing_count:<3} injuries "
              f"{e.injuries_count:<3} {e.outcome[:18]:<18} {e.status}")


def _event() -> M.Emergency | None:
    eid = _int("  Event ID: ")
    return M.get_emergency(eid) if eid else None


def _em_new(principal: Principal) -> None:
    e = M.create_emergency(_ask(_EM), actor=principal)
    print(f"  Created event #{e.event_id}.")


def _em_list(_principal: Principal) -> None:
    _em_table(M.list_emergencies(kind=_pick("Kind (blank = all)", M.EVENT_KINDS) or None,
                                 status=_pick("Status (blank = all)", M.EVENT_STATUSES) or None,
                                 outstanding_only=_yes("  Outstanding only?")))


def _em_view(_principal: Principal) -> None:
    e = _event()
    if e:
        print(f"\n  Event #{e.event_id}")
        _show(e, _EM)


def _em_edit(principal: Principal) -> None:
    e = _event()
    if e:
        M.update_emergency(e.event_id, _ask(_EM, e), actor=principal)
        print("  Saved.")


def _em_status(principal: Principal) -> None:
    e = _event()
    if e:
        M.set_emergency_status(e.event_id, _pick("Status", M.EVENT_STATUSES, e.status)
                               or e.status, actor=principal)
        print("  Status saved.")


def _em_close(principal: Principal) -> None:
    e = _event()
    if e:
        M.close_emergency(e.event_id, actor=principal)
        print("  Closed.")


def _em_summary(_principal: Principal) -> None:
    s = M.emergency_summary()
    print(f"\n  Total: {s['total']}   Drills: {s['drills']}   Real: {s['real']}   Outstanding: "
          f"{s['outstanding']}   Missing: {s['total_missing']}   Injuries: "
          f"{s['total_injuries']}   Services: {s['services_called']}   Avg min: "
          f"{s['avg_duration_min'] if s['avg_duration_min'] is not None else '-'}")
    for key in ("by_type", "by_outcome", "by_status"):
        print(f"  {key[3:].title()}: " + ", ".join(f"{k} {v}" for k, v in s[key].items()))
    d = M.drills_this_term()
    print(f"  Fire drill this term: {'yes' if d['this_term'] else 'NO'} (last {d['last'] or '-'})")


def _em_delete(principal: Principal) -> None:
    e = _event()
    if e and _yes(f"  Delete event #{e.event_id}?"):
        M.delete_emergency(e.event_id, actor=principal)
        print("  Deleted.")


# ── Conditions, allergies, medicines ─────────────────────────────────

_COND = [("condition", "Condition", None), ("severity", "Severity", M.CONDITION_SEVERITIES),
         ("symptoms", "Symptoms", None), ("triggers", "Triggers", None),
         ("what_to_do", "What to do", None),
         ("emergency_medication", "Emergency medication", None),
         ("medication_location", "Where it's kept", None),
         ("has_ihp", "Healthcare plan (y/n)", None), ("ihp_agreed_on", "IHP agreed on", None),
         ("ihp_review_date", "IHP review date", None), ("diagnosed_by", "Diagnosed by", None),
         ("status", "Status", M.CONDITION_STATUSES), ("notes", "Notes", None)]
_ALG = [("allergen", "Allergen", None), ("kind", "Kind", M.ALLERGY_KINDS),
        ("reaction", "Reaction", None), ("severity", "Severity", M.CONDITION_SEVERITIES),
        ("anaphylaxis", "Anaphylaxis (y/n)", None),
        ("auto_injector", "Carries auto-injector (y/n)", None),
        ("dietary", "Catering note", None), ("action", "What to do", None),
        ("status", "Status", M.CONDITION_STATUSES), ("notes", "Notes", None)]
_MED = [("name", "Medicine", None), ("form", "Form", M.MEDICINE_FORMS),
        ("strength", "Strength", None), ("dose", "Dose", None), ("frequency", "When", None),
        ("purpose", "What for", None), ("emergency", "Emergency medication (y/n)", None),
        ("controlled", "Controlled drug (y/n)", None), ("prescribed", "Prescribed (y/n)", None),
        ("location", "Where it's kept", None), ("quantity", "Quantity", None),
        ("expiry_date", "Expiry date", None), ("batch", "Batch", None),
        ("consent_on", "Consent form date", None), ("consent_by", "Consent given by", None),
        ("notes", "Notes", None)]


def _care(principal: Principal) -> None:
    year = _prompt("  Year group (blank = all): ")
    for r in M.care_list(actor=principal, year_group=year or None,
                         serious_only=_yes("  Severe / life-threatening only?")):
        print(f"\n  {r['pupil_name']} ({r['admission_no']}), Year {r['year_group']} - "
              f"{r['worst'].upper()}{' · IHP' if r['ihp'] else ''}")
        for label, key in (("Conditions", "conditions"), ("Allergies", "allergies"),
                           ("Medication", "medication")):
            if r[key]:
                print(f"    {label + ':':<12} " + "; ".join(r[key]))
        for w in r["what_to_do"]:
            print(f"    DO: {w}")


def _allergy_list(principal: Principal) -> None:
    refs = _prompt("  Pupil IDs for a trip (comma-separated, blank = year/all): ")
    ids = [p.pupil_id for p in (M._pupil(x.strip()) for x in refs.split(",") if x.strip()) if p]
    year = "" if ids else _prompt("  Year group (blank = all): ")
    rows = M.allergy_list(actor=principal, pupil_ids=ids or None, year_group=year or None)
    if not rows:
        print("  No allergies recorded.")
    for r in rows:
        print(f"  {r['pupil_name'][:24]:<24} Yr{r['year_group']:<3} {r['allergen'][:20]:<20} "
              f"{r['severity']:<16} {'ANAPHYLAXIS' if r['anaphylaxis'] else '':<12} "
              f"{'pen' if r['auto_injector'] else '':<4} {r['dietary']}  {r['action']}")


def _conditions(_principal: Principal) -> None:
    for c in M.list_conditions(year_group=_prompt("  Year group (blank = all): ") or None):
        print(f"  #{c.condition_id:<4} {c.pupil_name[:22]:<22} Yr{c.pupil_year:<3} "
              f"{c.condition[:26]:<26} {c.severity:<16} IHP review {c.ihp_review_date or '-'}")


def _add_condition(principal: Principal) -> None:
    c = M.add_condition({"pupil_id": _prompt("  Pupil ID / admission no.: "), **_ask(_COND)},
                        actor=principal)
    print(f"  Recorded #{c.condition_id}.")


def _edit_condition(principal: Principal) -> None:
    cid = _int("  Condition ID: ")
    if cid:
        M.update_condition(cid, _ask(_COND, M.get_condition(cid)), actor=principal)
        print("  Saved.")


def _ihp(principal: Principal) -> None:
    cid = _int("  Condition ID: ")
    if cid:
        c = M.review_ihp(cid, actor=principal,
                         reviewed_on=_prompt("  Reviewed on (blank = today): ") or None,
                         next_review=_prompt("  Next review (blank = 12 months): ") or None,
                         note=_prompt("  Note: "))
        print(f"  Next IHP review {c.ihp_review_date}.")


def _allergies(_principal: Principal) -> None:
    for a in M.list_allergies():
        print(f"  #{a.allergy_id:<4} {a.pupil_name[:22]:<22} {a.allergen[:20]:<20} {a.kind:<14} "
              f"{a.severity}{' ANAPHYLAXIS' if a.anaphylaxis else ''}")


def _add_allergy(principal: Principal) -> None:
    a = M.add_allergy({"pupil_id": _prompt("  Pupil ID / admission no.: "), **_ask(_ALG)},
                      actor=principal)
    print(f"  Recorded #{a.allergy_id}.")


def _medicines(_principal: Principal) -> None:
    for m in M.list_medicines():
        flag = "EXPIRED" if m.expired else ("expiring" if m.expiring else "")
        print(f"  #{m.medicine_id:<4} {m.pupil_name[:22]:<22} {m.label[:30]:<30} {m.dose:<12} "
              f"qty {m.quantity if m.quantity is not None else '-':<4} exp {m.expiry_date} "
              f"{flag:<8} {m.location}")


def _add_medicine(principal: Principal) -> None:
    m = M.add_medicine({"pupil_id": _prompt("  Pupil ID / admission no.: "), **_ask(_MED)},
                       actor=principal)
    print(f"  Recorded #{m.medicine_id}.")


def _give(principal: Principal) -> None:
    mid = _int("  Medicine ID (blank = not held in school): ")
    data: dict[str, Any] = {"medicine_id": mid} if mid else {
        "pupil_id": _prompt("  Pupil ID / admission no.: "),
        "medicine_name": _prompt("  Medicine: ")}
    if mid:
        m = M.get_medicine(mid)
        print(f"  {m.pupil_name}: {m.label}, {m.dose} {m.frequency or ''}")
        given = M.doses_today(m.pupil_id, m.medicine_id)
        if given:
            print(f"  ! Already given today at {', '.join(d.given_at[11:] for d in given)}")
    data.update({"dose": _prompt("  Dose (blank = usual): "),
                 "given_at": _prompt("  Given at (blank = now): "),
                 "given_by": _prompt("  Given by: "),
                 "witnessed_by": _prompt("  Witnessed by (controlled drugs): "),
                 "reason": _prompt("  Reason: "),
                 "consent_checked": _yes("  Consent and label checked?"),
                 "refused": _yes("  Refused?"), "emergency": _yes("  Emergency use?"),
                 "parent_informed": _yes("  Parent informed?")})
    d = M.give_dose(data, actor=principal)
    print(f"  Recorded dose #{d.dose_id} at {d.given_at}.")


def _doses(_principal: Principal) -> None:
    for d in M.list_doses(from_date=_prompt("  From (blank = any): ") or None, limit=200):
        print(f"  #{d.dose_id:<5} {d.given_at} {d.pupil_name[:22]:<22} {d.medicine_name[:20]:<20} "
              f"{d.dose:<12} by {d.given_by}{' REFUSED' if d.refused else ''}"
              f"{' EMERGENCY' if d.emergency else ''}")


def _return(principal: Principal) -> None:
    mid = _int("  Medicine ID: ")
    if mid:
        m = M.return_medicine(mid, actor=principal, disposed=_yes("  Disposed (not sent home)?"),
                              note=_prompt("  Note: "))
        print(f"  {m.status}.")


def _replace(principal: Principal) -> None:
    mid = _int("  Medicine ID: ")
    if mid:
        _deliver(principal, M.ask_for_replacement(mid, actor=principal,
                                                  note=_prompt("  Note (blank ok): ")))


def _told(principal: Principal) -> None:
    i = _incident()
    if i:
        M.record_parents_told(i.incident_id, actor=principal,
                              how=_pick("How", M.TOLD_HOW, "Phone call") or "Phone call",
                              when=_prompt("  When (blank = now): ") or None)
        print("  Recorded.")


def _riddor(principal: Principal) -> None:
    i = _incident()
    if i:
        M.record_riddor(i.incident_id, actor=principal,
                        reported_on=_prompt("  Reported on (blank = today): ") or None,
                        reference=_prompt("  HSE reference: "))
        print("  Recorded.")


def _notify(principal: Principal) -> None:
    i = _incident()
    if i:
        _deliver(principal, M.notify_parents(i.incident_id, actor=principal,
                                             note=_prompt("  Note (blank ok): ")))


def _due(_principal: Principal) -> None:
    rows = M.due()
    if not rows:
        print("  Nothing due.")
    for d in rows:
        print(f"  {d['due']} {'OVERDUE' if d['overdue'] else '':<8} {d['who'][:22]:<22} "
              f"{d['item']}")


def _summary(_principal: Principal) -> None:
    s = M.summary()
    print(f"\n  Conditions: {s['conditions']} ({s['pupils_with_conditions']} pupils, "
          f"{s['ihps']} IHPs)   Allergies: {s['allergies']} ({s['anaphylaxis']} anaphylaxis)"
          f"   Medicines: {s['medicines']} ({s['expiring']} expiring)   Doses today: "
          f"{s['doses_today']}")
    print("  By condition: " + ", ".join(f"{k} {v}" for k, v in s["by_condition"].items()))
    for r in M.dose_report():
        print(f"  {r['medicine'][:30]:<30} doses {r['doses']:<4} refused {r['refused']:<3} "
              f"emergency {r['emergency']:<3} pupils {r['pupils']}")


def _history(_principal: Principal) -> None:
    p = M._pupil(_prompt("  Pupil ID / admission no. (blank = all): "))
    for h in M.history(p.pupil_id if p else None):
        print(f"  {h['at']}  {h['actor']:<12} {h['item']:<10} {h['action']:<8} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    which = _pick("Export", ("Care list", "Allergy list", "First aid"), "Care list")
    path = _prompt("  Save CSV to: ")
    if not path:
        return
    fn = {"Allergy list": M.export_allergy_list, "First aid": M.export_first_aid}.get(
        which or "", M.export_care_list)
    print(f"  Exported {fn(path, actor=principal)} row(s).")


_OPTIONS = {"1": _fa_new, "2": _fa_list, "3": _fa_view, "4": _fa_edit, "5": _fa_summary,
            "6": _fa_delete, "7": _em_new, "8": _em_list, "9": _em_view, "10": _em_edit,
            "11": _em_status, "12": _em_close, "13": _em_summary, "14": _em_delete,
            "15": _care, "16": _allergy_list, "17": _conditions, "18": _add_condition,
            "19": _edit_condition, "20": _ihp, "21": _allergies, "22": _add_allergy,
            "23": _medicines, "24": _add_medicine, "25": _give, "26": _doses, "27": _return,
            "28": _replace, "29": _told, "30": _riddor, "31": _notify, "32": _due,
            "33": _summary, "34": _history, "35": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("medical.view")
        print("\n  ── Medical ──")
        print("  First aid\n   1) New incident\n   2) List incidents\n   3) View incident"
              "\n   4) Edit incident\n   5) Summary report\n   6) Delete incident")
        print("  More")
        print("   7) New emergency / drill\n   8) List events\n   9) View event\n  10) Edit event"
              "\n  11) Set event status\n  12) Close event\n  13) Emergency summary"
              "\n  14) Delete event\n  15) Who has what and what to do"
              "\n  16) Allergy list (trip / kitchen)\n  17) Conditions\n  18) Add condition"
              "\n  19) Edit condition\n  20) IHP reviewed\n  21) Allergies\n  22) Add allergy"
              "\n  23) Medicines in school\n  24) Add medicine\n  25) Give a medicine"
              "\n  26) Medicines given\n  27) Return / dispose medicine"
              "\n  28) Ask family to replace a medicine\n  29) Parents told (incident)"
              "\n  30) RIDDOR reported\n  31) E-mail family about an incident\n  32) Due"
              "\n  33) Summary\n  34) History\n  35) Export CSV")
        print("   0) Back")
        choice = _prompt("Select: ")
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
