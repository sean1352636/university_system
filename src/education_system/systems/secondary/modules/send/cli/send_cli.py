"""SEND in the terminal.

The old SEND menu keeps its options in place: 1 Add / update SEND record,
2 List register, 3 View record + review history, 4 Delete record, 5 Add
review, 6 Delete review, 7 Cohort summary, 8 Overdue reviews. The old
Accessibility menu follows under "More" (9-17: new, list, view, edit, set
status, pupil arrangements, expired, summary, delete), then: 18 Strategies
for teachers, 19 Plans, 20 Review a plan, 21 New plan, 22 Provision map,
23 Add provision, 24 External agencies, 25 Add agency referral, 26 Due,
27 Reports, 28 LA report / decision, 29 Invite family to a review, 30 Copy exam
access to SEN record, 31 History, 32 Export CSV. Rules live in
:mod:`modules.send.domain.send`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.send.domain import send as S
from education_system.systems.secondary.modules.pupils.domain import sen_details as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (S.ValidationError, S.PermissionDenied, S.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _ask(fields: list[tuple[str, str, Any]], current: Any = None) -> dict[str, Any]:
    """Ask each ``(key, label, choices)``; Enter keeps the current value,
    "-" clears it."""
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


def _pupil_ref() -> str:
    return _prompt("  Pupil ID / admission no.: ")


def _table(rows: list[S.Record]) -> None:
    if not rows:
        print("  (no records)")
        return
    print(f"  {'Adm no':<10} {'AYear':<8} {'Pupil':<24} {'Yr':<3} {'Stage':<28} "
          f"{'Primary need':<30} {'Status':<11} Next review")
    for r in rows:
        print(f"  {r.admission_no:<10} {r.academic_year:<8} {r.pupil_name[:24]:<24} "
              f"{r.year_group:<3} {r.stage[:28]:<28} {(r.primary_label or '-')[:30]:<30} "
              f"{r.status:<11} {r.next_review_date or '-'}")


# ── The old SEND menu ────────────────────────────────────────────────

def _upsert(principal: Principal) -> None:
    ref = _pupil_ref()
    cur = S.get(ref)
    print(f"  Current stage: {cur.stage}")
    data: dict[str, Any] = {}
    st = _pick("Stage", S.STAGES, cur.stage)
    if st and st != cur.stage:
        data["stage"] = st
    print("  Need codes: " + ", ".join(SD.NEEDS))
    data.update(_ask([("primary_need", "Primary need (code)", None),
                      ("secondary_need", "Secondary need (code)", None),
                      ("status", "Status", S.STATUSES), ("senco", "SENCo", None),
                      ("keyworker", "Keyworker", None), ("added_on", "Start date", None),
                      ("next_review_date", "Next review", None),
                      ("ehcp_reference", "EHCP reference", None),
                      ("ehcp_issued_on", "EHCP issued on", None),
                      ("provision", "Provision summary", None), ("diagnosis", "Diagnosis", None),
                      ("strategies", "Strategies for staff", None),
                      ("exam_access", "Exam access", None), ("notes", "Notes", None)], cur))
    r = S.save_record(ref, data, actor=principal)
    print(f"  Saved: {r.pupil_name} ({r.admission_no}) - {r.stage}, {r.status}")


def _list(_principal: Principal) -> None:
    year = _prompt("  Year group (blank = all): ")
    stage = _pick("Stage (blank = all)", S.STAGES)
    status = _pick("Status (blank = all)", S.STATUSES)
    rows = S.list_records(year_group=year or None, stage=stage or None, status=status or None)
    print(f"\n  {len(rows)} SEND record(s):")
    _table(rows)


def _view(_principal: Principal) -> None:
    s = S.record_summary(_pupil_ref())
    r = s["record"]
    print(f"\n  ── SEND record: {r.pupil_name} ({r.admission_no}), Year {r.year_group} ──")
    for label, v in (("Stage", r.stage), ("Status", r.status),
                     ("Primary need", f"{r.primary_label} ({r.primary_need})"
                      if r.primary_need else None),
                     ("Secondary", SD.NEEDS.get(r.secondary_need or "")),
                     ("Area", r.area), ("SENCo", r.senco), ("Keyworker", r.keyworker),
                     ("Parent", s["parent_contact"]), ("EHCP ref", r.ehcp_reference),
                     ("EHCP issued", r.ehcp_issued_on), ("Annual review due", s["ehcp_due"]),
                     ("Assessment", r.ehcna_status), ("Diagnosis", r.diagnosis),
                     ("Start", r.added_on), ("Next review", r.next_review_date),
                     ("Provision", r.provision), ("Strategies", r.strategies),
                     ("Exam access", r.exam_access), ("Notes", r.notes)):
        if v:
            print(f"    {label + ':':<18} {v}")
    print(f"\n  Reviews: {s['review_count']}    Last: {s['last_review'] or '-'}")
    for v in s["reviews"]:
        print(f"    #{v.review_id:<4} {v.review_date} {v.review_type:<22} {v.outcome:<10} "
              f"next {v.next_review_date or '-'}  {(v.progress or '')[:40]}")
    for pl in s["plans"]:
        print(f"    Plan #{pl.plan_id} {pl.kind} cycle {pl.cycle} ({pl.status}) review "
              f"{pl.review_date or '-'}")
    for x in s["provision"]:
        print(f"    Provision #{x.provision_id} {x.provision} {x.hours_per_week}h/wk "
              f"x{x.weeks} £{x.cost:.2f} ({x.status})")
    for a in s["access"]:
        print(f"    Access #{a.arrangement_id} {a.category} ({a.status})")
    for g in s["agencies"]:
        print(f"    Agency #{g.agency_id} {g.agency} ({g.status})")


def _delete(principal: Principal) -> None:
    ref = _pupil_ref()
    if _yes("  Delete the register entry? (plans, reviews and the SEN status stay)"):
        print("  Deleted." if S.delete(ref, actor=principal) else "  No register entry.")


def _add_review(principal: Principal) -> None:
    data: dict[str, Any] = {"pupil_id": _pupil_ref(),
                            "review_type": _pick("Type", S.REVIEW_TYPES, S.REVIEW_TYPES[0]),
                            "outcome": _pick("Outcome", S.REVIEW_OUTCOMES, S.DEFAULT_OUTCOME)}
    for key, label in (("review_date", "Date (blank = today)"), ("reviewer", "Reviewer"),
                       ("attendees", "Attendees"), ("progress", "Progress"),
                       ("adjustments", "Adjustments"), ("pupil_views", "Pupil's views"),
                       ("parent_views", "Family's views"),
                       ("next_review_date", "Next review (blank = default)"),
                       ("notes", "Notes")):
        v = _prompt(f"  {label}: ")
        if v:
            data[key] = v
    r = S.add_review(data, actor=principal)
    print(f"  Added review #{r.review_id} ({r.outcome}, next {r.next_review_date or '-'}).")


def _delete_review(principal: Principal) -> None:
    rid = _int("  Review ID: ")
    if rid and _yes(f"  Delete review #{rid}?"):
        S.delete_review(rid, actor=principal)
        print(f"  Deleted review #{rid}.")


def _summary(_principal: Principal) -> None:
    year = _prompt("  Year group (blank = all): ")
    s = S.cohort_summary(year_group=year or None)
    print(f"\n  Total: {s['total']}    SEN support: {s['support_count']}    EHCP: "
          f"{s['ehcp_count']}    Monitoring: {s['monitoring']}    On roll: {s['on_roll']}")
    for key in ("by_stage", "by_primary_need", "by_status"):
        print(f"  {key[3:].replace('_', ' ').title()}: "
              + ", ".join(f"{k} {v}" for k, v in s[key].items()))


def _overdue(_principal: Principal) -> None:
    rows = S.overdue_reviews()
    print(f"\n  {len(rows)} record(s) with overdue reviews")
    _table(rows)


# ── The old Accessibility menu ───────────────────────────────────────

_ACC_FIELDS = [("arrangement_type", "Type", S.ACCESS_TYPES),
               ("category", "Category", S.ACCESS_CATEGORIES),
               ("description", "Description", None), ("exam_only", "Exam only (y/n)", None),
               ("start_date", "Start date", None), ("end_date", "End date", None),
               ("status", "Status", S.ACCESS_STATUSES),
               ("evidence_source", "Evidence source", S.EVIDENCE_SOURCES),
               ("evidence_reference", "Evidence reference", None),
               ("assessor", "Assessor (Form 8)", None), ("assessed_on", "Assessed on", None),
               ("approved_by", "Approved by", None), ("approval_date", "Approval date", None),
               ("review_date", "Review date", None), ("notes", "Notes", None)]


def _acc_table(rows: list[S.Arrangement]) -> None:
    if not rows:
        print("  (no arrangements)")
        return
    for a in rows:
        print(f"  #{a.arrangement_id:<4} {a.pupil_name[:22]:<22} {a.pupil_year:<3} "
              f"{a.arrangement_type[:22]:<22} {a.category[:22]:<22} {a.status:<12} "
              f"{'exam' if a.exam_only else '':<5} {a.start_date} - {a.end_date or ''}")


def _acc_new(principal: Principal) -> None:
    a = S.add_arrangement({"pupil_id": _pupil_ref(), **_ask(_ACC_FIELDS)}, actor=principal)
    print(f"  Created arrangement #{a.arrangement_id} ({a.status}).")


def _acc_list(_principal: Principal) -> None:
    year = _prompt("  Year group (blank = all): ")
    t = _pick("Type (blank = all)", S.ACCESS_TYPES)
    st = _pick("Status (blank = all)", S.ACCESS_STATUSES)
    _acc_table(S.list_arrangements(year_group=year or None, arrangement_type=t or None,
                                   status=st or None,
                                   exam_only=True if _yes("  Exam only?") else None))


def _acc(principal: Principal) -> S.Arrangement | None:
    aid = _int("  Arrangement ID: ")
    return S.get_arrangement(aid) if aid else None


def _acc_view(principal: Principal) -> None:
    a = _acc(principal)
    if a:
        print(f"\n  #{a.arrangement_id} {a.pupil_name} ({a.admission_no})")
        for key, label, _c in _ACC_FIELDS:
            v = getattr(a, key)
            if v not in (None, "", False):
                print(f"    {label + ':':<22} {v}")


def _acc_edit(principal: Principal) -> None:
    a = _acc(principal)
    if a:
        S.update_arrangement(a.arrangement_id, _ask(_ACC_FIELDS, a), actor=principal)
        print("  Saved.")


def _acc_status(principal: Principal) -> None:
    a = _acc(principal)
    if a:
        st = _pick("Status", S.ACCESS_STATUSES, a.status)
        by = _prompt("  Approved by (blank = keep): ") if st == "Active" else ""
        S.set_arrangement_status(a.arrangement_id, st or a.status, actor=principal,
                                 approved_by=by or None)
        print("  Status saved.")


def _acc_pupil(_principal: Principal) -> None:
    p = S._pupil(_pupil_ref())
    if p is None:
        print("  No such pupil.")
        return
    _acc_table(S.list_arrangements(pupil_id=p.pupil_id))


def _acc_expired(principal: Principal) -> None:
    rows = S.expired_arrangements()
    _acc_table(rows)
    if rows and _yes("  Mark these Expired?"):
        print(f"  {S.expire_overdue(actor=principal)} marked expired.")


def _acc_summary(_principal: Principal) -> None:
    s = S.access_summary(year_group=_prompt("  Year group (blank = all): ") or None)
    print(f"\n  Total: {s['total']}   Exam only: {s['exam_only']}   Expired: {s['expired']}   "
          f"Pupils with active: {s['pupils']}")
    for key in ("by_type", "by_category", "by_status"):
        print(f"  {key[3:].title()}: " + ", ".join(f"{k} {v}" for k, v in s[key].items()))


def _acc_delete(principal: Principal) -> None:
    a = _acc(principal)
    if a and _yes(f"  Delete arrangement #{a.arrangement_id}?"):
        S.delete_arrangement(a.arrangement_id, actor=principal)
        print("  Deleted.")


# ── New ──────────────────────────────────────────────────────────────

def _strategies(principal: Principal) -> None:
    mine = _yes("  Only pupils in my teaching groups?")
    year = "" if mine else _prompt("  Year group (blank = all): ")
    for r in S.strategies(actor=principal, year_group=year or None, mine=mine):
        print(f"\n  {r['pupil_name']} ({r['admission_no']}), Year {r['year_group']} "
              f"{r['form_group'] or ''} - {r['stage']}")
        for label in ("needs", "strategies", "adjustments", "exam_access", "keyworker"):
            if r[label]:
                print(f"    {label.replace('_', ' ').capitalize() + ':':<14} "
                      + r[label].replace("\n", "\n" + " " * 19))


def _plans(_principal: Principal) -> None:
    ref = _prompt("  Pupil ID / admission no. (blank = all active): ")
    p = S._pupil(ref) if ref else None
    rows = S.list_plans(pupil_id=p.pupil_id) if p else S.list_plans(status="Active")
    if not rows:
        print("  (no plans)")
    for pl in rows:
        print(f"  #{pl.plan_id:<4} {pl.pupil_name[:22]:<22} {pl.kind:<18} cycle {pl.cycle:<2} "
              f"{pl.status:<9} {pl.start_date} review {pl.review_date or '-'}")
    if p and rows and _yes("  Show the newest plan?"):
        print("\n" + S.plan_text(rows[0]))


_PLAN_FIELDS = [("kind", "Kind", S.PLAN_KINDS), ("title", "Title", None),
                ("start_date", "Start date", None), ("review_date", "Review date", None),
                ("assess", "Assess - what we know", None),
                ("outcomes", "Plan - outcomes", None), ("provision", "Do - support", None),
                ("strategies", "Strategies", None), ("pupil_voice", "Pupil's views", None),
                ("parent_voice", "Family's views", None),
                ("status", "Status", S.PLAN_STATUSES)]


def _new_plan(principal: Principal) -> None:
    pl = S.create_plan({"pupil_id": _pupil_ref(), **_ask(_PLAN_FIELDS)}, actor=principal)
    print(f"  Created plan #{pl.plan_id} (cycle {pl.cycle}, review {pl.review_date}).")
    if _yes("  E-mail it to the family?"):
        _deliver(principal, S.share_plan(pl.plan_id, actor=principal))


def _review_plan(principal: Principal) -> None:
    pid = _int("  Plan ID: ")
    if not pid:
        return
    data: dict[str, Any] = {"outcome": _pick("Outcome", S.REVIEW_OUTCOMES, S.DEFAULT_OUTCOME)}
    for key, label in (("review_notes", "How did it go"), ("reviewed_on", "Reviewed on"),
                       ("reviewer", "Reviewer"), ("attendees", "Attendees"),
                       ("pupil_views", "Pupil's views"), ("parent_views", "Family's views"),
                       ("next_review_date", "Next review")):
        v = _prompt(f"  {label}: ")
        if v:
            data[key] = v
    data["next_cycle"] = data["outcome"] != "Discharge" and _yes("  Start the next cycle?")
    res = S.review_plan(pid, data, actor=principal)
    print(f"  Reviewed (review #{res['review'].review_id})."
          + (f" Next cycle: plan #{res['next'].plan_id}." if res["next"] else ""))


_PROV_FIELDS = [("provision", "Provision", None), ("need_area", "Area", S.NEED_AREAS),
                ("provider", "Provider", None), ("delivery", "Delivery", S.DELIVERY),
                ("group_size", "Group size", None), ("hours_per_week", "Hours a week", None),
                ("weeks", "Weeks", None), ("cost_per_hour", "Cost per hour £", None),
                ("fixed_cost", "Fixed cost £ (instead)", None),
                ("start_date", "Start date", None), ("end_date", "End date", None),
                ("status", "Status", S.PROVISION_STATUSES),
                ("in_ehcp", "In the EHC plan (y/n)", None), ("outcome", "Outcome", None),
                ("notes", "Notes", None)]


def _provision_map(_principal: Principal) -> None:
    year = _prompt(f"  School year [{S.current_year()}]: ") or None
    rows = S.provision_map(academic_year=year)
    print(f"\n  {'Provision':<32} {'Pupils':>6} {'Hours':>8} {'Cost £':>10}  Areas")
    for g in rows:
        print(f"  {g['provision'][:32]:<32} {g['pupils']:>6} {g['hours']:>8} "
              f"{g['cost']:>10,.2f}  {g['areas']}")
    print(f"  {'Total':<32} {'':>6} {sum(g['hours'] for g in rows):>8} "
          f"{sum(g['cost'] for g in rows):>10,.2f}")


def _add_provision(principal: Principal) -> None:
    refs = _prompt("  Pupil IDs / admission nos. (comma-separated): ")
    ids = [p.pupil_id for p in (S._pupil(r.strip()) for r in refs.split(",") if r.strip()) if p]
    data = _ask(_PROV_FIELDS)
    rows = S.add_provision_many(ids, data, actor=principal)
    print(f"  Added for {len(rows)} pupil(s).")


def _agencies(_principal: Principal) -> None:
    for g in S.list_agencies():
        print(f"  #{g.agency_id:<4} {g.pupil_name[:22]:<22} {g.agency[:26]:<26} {g.status:<10} "
              f"referred {g.referred_on or '-'} next {g.next_appointment or '-'}")


def _add_agency(principal: Principal) -> None:
    data = _ask([("agency", "Agency", S.AGENCIES), ("contact_name", "Contact", None),
                 ("contact_details", "Contact details", None),
                 ("referred_on", "Referred on", None), ("referred_by", "Referred by", None),
                 ("status", "Status", S.AGENCY_STATUSES),
                 ("next_appointment", "Next appointment", None), ("notes", "Notes", None)])
    g = S.add_agency({"pupil_id": _pupil_ref(), **data}, actor=principal)
    print(f"  Recorded #{g.agency_id}.")


def _due(_principal: Principal) -> None:
    rows = S.due()
    if not rows:
        print("  Nothing due in the next 30 days.")
    for d in rows:
        print(f"  {d['due']} {'OVERDUE' if d['overdue'] else '':<8} {d['pupil_name'][:22]:<22} "
              f"Yr{d['year_group']:<3} {d['item']}")


def _reports(_principal: Principal) -> None:
    print(f"\n  Primary need by year\n  {'Need':<6} {'Label':<44} "
          + " ".join(f"Y{y:<3}" for y in S.P.YEAR_GROUPS) + " Total")
    for r in S.needs_by_year():
        print(f"  {r['need']:<6} {r['label'][:44]:<44} "
              + " ".join(f"{r[y]:<4}" for y in S.P.YEAR_GROUPS) + f" {r['total']}")
    print("\n  SEN support (K) and EHC plans (E) by year")
    for r in S.stage_by_year():
        print(f"  Year {r['year']:<3} on roll {r['on_roll']:<4} K {r['K']:<4} "
              f"({r['k_pct'] if r['k_pct'] is not None else '-'}%)  E {r['E']:<4} "
              f"({r['e_pct'] if r['e_pct'] is not None else '-'}%)  monitoring {r['monitoring']}")
    print("\n  By area of need: " + ", ".join(f"{r['area']} {r['pupils']}" for r in S.by_area()))


def _la(principal: Principal) -> None:
    rid = _int("  Annual review ID: ")
    if rid:
        rv = S.record_la(rid, actor=principal,
                         report_sent_on=_prompt("  Report sent on (blank = keep): ") or None,
                         decision=_pick("LA decision (blank = not yet)", S.LA_DECISIONS),
                         decision_on=_prompt("  Decision date (blank = today): ") or None)
        print(f"  Saved: report {rv.la_report_sent_on or '-'}, decision {rv.la_decision or '-'}")


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


def _invite(principal: Principal) -> None:
    ref = _pupil_ref()
    res = S.invite_to_review(ref, actor=principal, when=_prompt("  When: "),
                             review_type=_pick("Type", S.REVIEW_TYPES, S.REVIEW_TYPES[0])
                             or S.REVIEW_TYPES[0],
                             where=_prompt("  Where: "), note=_prompt("  Note (blank ok): "))
    _deliver(principal, res)


def _copy_access(principal: Principal) -> None:
    d = S.copy_exam_access(S._need_pupil(_pupil_ref()).pupil_id, actor=principal)
    print(f"  SEN record exam access: {d.exam_access or '(none)'}")


def _history(_principal: Principal) -> None:
    p = S._pupil(_prompt("  Pupil ID / admission no. (blank = all): "))
    for h in S.history(p.pupil_id if p else None):
        print(f"  {h['at']}  {h['actor']:<12} {h['item']:<10} {h['action']:<10} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. send_register.csv): ")
    if path:
        print(f"  Exported {S.export_csv(path, actor=principal)} record(s).")


_OPTIONS = {"1": _upsert, "2": _list, "3": _view, "4": _delete, "5": _add_review,
            "6": _delete_review, "7": _summary, "8": _overdue, "9": _acc_new, "10": _acc_list,
            "11": _acc_view, "12": _acc_edit, "13": _acc_status, "14": _acc_pupil,
            "15": _acc_expired, "16": _acc_summary, "17": _acc_delete, "18": _strategies,
            "19": _plans, "20": _review_plan, "21": _new_plan, "22": _provision_map,
            "23": _add_provision, "24": _agencies, "25": _add_agency, "26": _due,
            "27": _reports, "28": _la, "29": _invite, "30": _copy_access, "31": _history,
            "32": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("send.view")
        print("\n  ── SEND ──")
        print("  Records\n    1) Add / update SEND record\n    2) List register"
              "\n    3) View record + review history\n    4) Delete record")
        print("  Reviews\n    5) Add review\n    6) Delete review")
        print("  Reports\n    7) Cohort summary\n    8) Overdue reviews")
        print("  More")
        print("    9) New access arrangement\n   10) List arrangements\n   11) View arrangement"
              "\n   12) Edit arrangement\n   13) Set arrangement status"
              "\n   14) Pupil arrangements\n   15) Expired (Active but past end-date)"
              "\n   16) Arrangements summary\n   17) Delete arrangement"
              "\n   18) Strategies for teachers\n   19) Plans\n   20) Review a plan"
              "\n   21) New plan\n   22) Provision map\n   23) Add provision"
              "\n   24) External agencies\n   25) Add agency referral\n   26) Due"
              "\n   27) Reports\n   28) LA report / decision (annual review)"
              "\n   29) Invite family to a review\n   30) Copy exam access to SEN record"
              "\n   31) History\n   32) Export CSV")
        print("    0) Back")
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
