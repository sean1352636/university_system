"""Appraisals & CPD in the terminal.

The old Appraisals menu keeps its numbering (its section headings took 1, 16
and 22): 2 List all, 3 Open only, 4 Mid-year overdue, 5 Filter, 6 Per-staff,
7 View, 8 New appraisal, 9 Edit appraisal, 10 Mark objectives set, 11 Record
mid-year, 12 Record end-year, 13 Close appraisal, 14 Change status, 15 Delete
appraisal, 17 List objectives, 18 Add objective, 19 Edit objective,
20 Change objective status, 21 Delete objective, 23 Summary. New: 24 CPD
(the old CPD menu, numbering kept), 25 Start the cycle, 26 Observations,
27 New observation, 28 Edit observation, 29 Respond to an observation,
30 Delete observation, 31 Statutory training, 32 Training due / overdue,
33 Record training, 34 Edit training, 35 Delete training, 36 Export CSV.

The CPD menu keeps the old one (headings at 1, 11 and 25): 2 List all,
3 Upcoming, 4 Completed, 5 Filter, 6 New activity, 7 Edit activity, 8 Mark
completed, 9 Change status, 10 Delete activity, 12 List all records,
13 Awaiting certificate, 14 Completed, 15 Per-staff, 16 For activity,
17 Filter, 18 New record, 19 Edit record, 20 Mark attended, 21 Record
evaluation, 22 File certificate, 23 Change status, 24 Delete record,
26 Summary; new: 27 Request training, 28 Approve / decline a request,
29 Withdraw, 30 CPD log, 31 Budget, 32 Set the budget, 33 Export CSV.
Rules: :mod:`modules.staff.domain.appraisals` and :mod:`appraisals_cpd`.
"""

from __future__ import annotations

from typing import Callable

from education_system.systems.secondary.modules.staff.cli.staff_directory_cli import (
    Field,
    ask_fields,
)
from education_system.systems.secondary.modules.staff.domain import appraisals as AP
from education_system.systems.secondary.modules.staff.domain import appraisals_cpd as CP
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (AP.ValidationError, AP.PermissionDenied, AP.NotFound)
_int = prompts.ask_int

_APPRAISAL: list[Field] = [
    ("appraiser_id", "Appraiser (staff code)", None), ("job_role", "Job role", None),
    ("self_review_completed", "Self review completed", "bool"),
    ("upholding_standards", "Upholding standards", "bool"), ("strengths", "Strengths", None),
    ("areas_to_develop", "Areas to develop", None), ("cpd_needs", "CPD needs", None),
    ("appraiser_comments", "Appraiser comments", None),
    ("appraisee_comments", "Appraisee comments", None), ("notes", "Notes", None)]
_OWN: list[Field] = [("appraisee_comments", "Your comments", None),
                     ("self_review_completed", "Self review completed", "bool")]
_OBJECTIVE: list[Field] = [
    ("objective_type", "Type", AP.OBJECTIVE_TYPES), ("title", "Title", None),
    ("description", "Description", None), ("target_metric", "Target", None),
    ("success_criteria", "Success criteria", None), ("progress_notes", "Progress notes", None),
    ("progress_percent", "Progress %", None), ("mid_year_progress", "Mid-year progress", None),
    ("end_year_evidence", "End-year evidence", None), ("weighting", "Weighting", None),
    ("notes", "Notes", None)]
_OWN_OBJECTIVE: list[Field] = [("progress_notes", "Progress notes", None),
                               ("progress_percent", "Progress %", None)]
_OBSERVATION: list[Field] = [
    ("observed_on", "Date (blank = today)", None),
    ("observation_type", "Type", AP.OBSERVATION_TYPES), ("class_observed", "Class", None),
    ("focus", "Focus", None), ("strengths", "Strengths", None),
    ("development_points", "Development points", None), ("judgement", "Judgement",
                                                          AP.JUDGEMENTS),
    ("feedback_given_on", "Feedback given on", None), ("notes", "Notes", None)]
_ACTIVITY: list[Field] = [
    ("title", "Title", None), ("provider", "Provider", None),
    ("activity_type", "Type", AP.ACTIVITY_TYPES), ("activity_date", "Date", None),
    ("end_date", "End date", None), ("hours", "Hours", None), ("cost", "Cost (£)", None),
    ("certificated", "Certificated", "bool"), ("accreditor", "Accreditor", None),
    ("location", "Location", None), ("capacity", "Capacity", None),
    ("organiser", "Organiser", None), ("description", "Description", None),
    ("outcomes", "Outcomes", None), ("status", "Status", AP.ACTIVITY_STATUSES),
    ("notes", "Notes", None)]
_REQUEST: list[Field] = [
    ("activity_id", "Catalogue activity id (blank ok)", None), ("title", "Title", None),
    ("provider", "Provider", None), ("start_date", "Start date", None),
    ("end_date", "End date", None), ("cost", "Cost (£)", None),
    ("cover_needed", "Cover needed", "bool"), ("cover_days", "Cover days", None),
    ("reason", "Why / what for", None)]
_TRAINING: list[Field] = [
    ("training_type", "Training", tuple(AP.TRAINING_TYPES)),
    ("completed_on", "Completed on", None), ("expires_on", "Expires on (blank = worked out)",
                                             None),
    ("provider", "Provider", None), ("certificate_ref", "Certificate", None),
    ("notes", "Notes", None)]


def _table(rows: list[AP.Appraisal]) -> None:
    if not rows:
        print("\n  (no appraisals)")
        return
    for i, a in enumerate(rows, 1):
        flag = "!" if a.mid_year_overdue else " "
        print(f"    {i:>3}){flag} #{a.appraisal_id:<4} {a.staff_name[:22]:<22} {a.academic_year:<8} "
              f"appraiser {(a.appraiser_name or '-')[:18]:<18} grade {a.overall_grade or '—'}  "
              f"pay {a.pay_progression:<8} [{a.status}]  {a.objectives} obj")


def _appraisal(p: Principal) -> AP.Appraisal | None:
    aid = _int("  Appraisal #: ")
    return AP.get_appraisal(aid, actor=p) if aid else None


def _list(p: Principal) -> None:
    _table(AP.list_appraisals(actor=p))


def _open(p: Principal) -> None:
    _table(AP.list_appraisals(actor=p, open_only=True))


def _overdue(p: Principal) -> None:
    _table(AP.list_appraisals(actor=p, mid_year_overdue=True))


def _filter(p: Principal) -> None:
    cycle = prompts.pick("Cycle (blank = all)", AP.list_cycles())
    st = prompts.pick("Status (blank = all)", AP.STATUSES)
    _table(AP.list_appraisals(actor=p, academic_year=cycle or None, status=st or None))


def _per_staff(p: Principal) -> None:
    m = SD.find(_prompt("  Staff (code / username): "))
    if m:
        _table(AP.list_appraisals(actor=p, staff_id=m.staff_id))


def _view(p: Principal) -> None:
    a = _appraisal(p)
    if a:
        print("\n" + "\n".join("  " + x for x in AP.appraisal_text(a.appraisal_id, actor=p)
                               .splitlines()))


def _new(p: Principal) -> None:
    data = {"staff_id": _prompt("  Staff (code / username): "),
            "academic_year": _prompt(f"  Cycle [{AP.current_year()}]: ") or None,
            **ask_fields(_APPRAISAL)}
    a = AP.create_appraisal(data, actor=p)
    print(f"  ✓ Appraisal #{a.appraisal_id} for {a.staff_name} ({a.academic_year}), "
          f"appraiser {a.appraiser_name or '(none)'}")


def _edit(p: Principal) -> None:
    a = _appraisal(p)
    if a:
        fields = _APPRAISAL if AP.can_manage_appraisal(p, a) else _OWN
        AP.update_appraisal(a.appraisal_id, ask_fields(fields, a), actor=p)
        print("  ✓ Saved.")


def _set_objectives(p: Principal) -> None:
    a = _appraisal(p)
    if a:
        AP.set_objectives(a.appraisal_id, actor=p,
                          on=_prompt("  Objectives set on (blank = today): ") or None)
        print("  ✓ Objectives set.")


def _mid_year(p: Principal) -> None:
    a = _appraisal(p)
    if a:
        AP.record_mid_year(a.appraisal_id, actor=p,
                           reviewed_on=_prompt("  Reviewed on (blank = today): ") or None,
                           notes=_prompt("  Notes: ") or None)
        print("  ✓ Mid-year review recorded.")


def _end_year(p: Principal) -> None:
    a = _appraisal(p)
    if a is None:
        return
    grade = prompts.pick("Overall grade", [f"{g} {AP.GRADE_LABELS[g]}" for g in AP.GRADES])
    a = AP.record_end_year(
        a.appraisal_id, actor=p, reviewed_on=_prompt("  Reviewed on (blank = today): ") or None,
        overall_grade=grade or None, outcome=prompts.pick("Outcome", AP.OUTCOMES),
        pay_progression=prompts.pick("Pay progression", AP.PAY_PROGRESSION),
        upholding_standards=_yes("  Upholding the Teachers' Standards?"),
        strengths=_prompt("  Strengths: ") or None,
        areas_to_develop=_prompt("  Areas to develop: ") or None,
        cpd_needs=_prompt("  CPD needs: ") or None,
        appraiser_comments=_prompt("  Appraiser comments: ") or None,
        pay_notes=_prompt("  Pay recommendation notes: ") or None)
    print(f"  ✓ Completed: grade {a.overall_grade or '—'} ({a.grade_label}), pay "
          f"{a.pay_progression}")


def _close(p: Principal) -> None:
    a = _appraisal(p)
    if a and _yes(f"  Close #{a.appraisal_id}?"):
        AP.close_appraisal(a.appraisal_id, actor=p)
        print("  ✓ Closed.")


def _status(p: Principal) -> None:
    a = _appraisal(p)
    if a:
        st = prompts.pick("Status", AP.STATUSES, a.status)
        AP.set_appraisal_status(a.appraisal_id, st or a.status, actor=p)
        print("  ✓ Saved.")


def _delete(p: Principal) -> None:
    a = _appraisal(p)
    if a and _yes(f"  Delete appraisal #{a.appraisal_id} and its objectives?"):
        AP.delete_appraisal(a.appraisal_id, actor=p)
        print("  ✓ Deleted.")


def _objectives(p: Principal) -> None:
    a = _appraisal(p)
    if a:
        for o in AP.list_objectives(a.appraisal_id, actor=p):
            pct = f" {o.progress_percent}%" if o.progress_percent is not None else ""
            print(f"    #{o.objective_id:<4} {o.objective_number}. [{o.status}] {o.title} "
                  f"({o.objective_type}){pct}")


def _add_objective(p: Principal) -> None:
    a = _appraisal(p)
    if a:
        o = AP.add_objective(a.appraisal_id, ask_fields(_OBJECTIVE), actor=p)
        print(f"  ✓ Objective {o.objective_number} added.")


def _objective() -> AP.Objective | None:
    oid = _int("  Objective #: ")
    return AP.get_objective(oid) if oid else None


def _edit_objective(p: Principal) -> None:
    o = _objective()
    if o:
        a = AP.get_appraisal(o.appraisal_id, actor=p)
        fields = _OBJECTIVE if AP.can_manage_appraisal(p, a) else _OWN_OBJECTIVE
        AP.update_objective(o.objective_id, ask_fields(fields, o), actor=p)
        print("  ✓ Saved.")


def _objective_status(p: Principal) -> None:
    o = _objective()
    if o:
        st = prompts.pick("Status", AP.OBJECTIVE_STATUSES, o.status)
        AP.set_objective_status(o.objective_id, st or o.status, actor=p)
        print("  ✓ Saved.")


def _delete_objective(p: Principal) -> None:
    o = _objective()
    if o and _yes(f"  Delete '{o.title}'?"):
        AP.delete_objective(o.objective_id, actor=p)
        print("  ✓ Deleted.")


def _summary(p: Principal) -> None:
    s = CP.summary(actor=p)
    print(f"\n  Appraisals {s['year']}: {s['appraisals']} ({s['open']} open, {s['completed']} "
          f"completed, {s['mid_year_overdue']} mid-year overdue, {s['no_appraiser']} without an "
          f"appraiser)")
    for title, key in (("By status", "by_status"), ("By grade", "by_grade"),
                       ("Pay progression", "pay")):
        if s[key]:
            print(f"  {title}: " + ", ".join(f"{k} {n}" for k, n in s[key].items()))
    b = s["budget"]
    print(f"  CPD: {s['records']} records, {s['requests']} waiting, {s['attended']} attended "
          f"({s['hours']:g} h), {s['awaiting_cert']} awaiting certificate, average rating "
          f"{s['average_rating']}")
    print("  Budget: " + (f"£{b['used']:,.2f} used of £{b['available']:,.2f}"
                          if b["available"] is not None else "not set"))
    print(f"  Statutory training missing / overdue: {s['training_overdue']}")


def _start_cycle(p: Principal) -> None:
    r = AP.start_cycle(_prompt(f"  Academic year [{AP.current_year()}]: ") or None, actor=p)
    print(f"  ✓ Opened {len(r['created'])} appraisal(s).")
    if r["no_appraiser"]:
        print("  ⚠ No line manager, so no appraiser yet: " + ", ".join(r["no_appraiser"]))


def _observations(p: Principal) -> None:
    for o in AP.list_observations(actor=p):
        print(f"    #{o.observation_id:<4} {o.observed_on} {o.staff_name[:22]:<22} "
              f"{o.observation_type:<18} by {(o.observer_name or '-')[:18]:<18} "
              f"{o.judgement or ''}")


def _new_observation(p: Principal) -> None:
    data = {"staff_id": _prompt("  Teacher observed (code / username): "),
            "observer_id": _prompt("  Observer (blank = you): "), **ask_fields(_OBSERVATION)}
    o = AP.add_observation(data, actor=p)
    print(f"  ✓ Observation #{o.observation_id}"
          + (f" linked to appraisal #{o.appraisal_id}" if o.appraisal_id else ""))


def _observation(p: Principal) -> AP.Observation | None:
    oid = _int("  Observation #: ")
    return AP.get_observation(oid, actor=p) if oid else None


def _edit_observation(p: Principal) -> None:
    o = _observation(p)
    if o:
        AP.update_observation(o.observation_id, ask_fields(_OBSERVATION, o), actor=p)
        print("  ✓ Saved.")


def _respond(p: Principal) -> None:
    o = _observation(p)
    if o:
        AP.update_observation(o.observation_id, {"staff_response": _prompt("  Response: ")},
                              actor=p)
        print("  ✓ Saved.")


def _delete_observation(p: Principal) -> None:
    o = _observation(p)
    if o and _yes("  Delete this observation?"):
        AP.delete_observation(o.observation_id, actor=p)
        print("  ✓ Deleted.")


def _training(p: Principal) -> None:
    for t in CP.list_training(actor=p):
        print(f"    #{t.training_id:<4} {t.staff_name[:22]:<22} {t.training_type:<22} "
              f"{t.completed_on}  expires {t.expires_on or '-'}"
              + ("  EXPIRED" if t.expired else ""))


def _due(p: Principal) -> None:
    rows = CP.training_due(actor=p)
    if not rows:
        print("  Nothing missing, overdue or due soon.")
    for d in rows:
        print(f"    {d['state']:<9} {d['staff'][:22]:<22} {d['training_type']:<22} "
              f"last {d['last_completed'] or '-':<10} expires {d['expires_on'] or '-'}")


def _add_training(p: Principal) -> None:
    t = CP.add_training({"staff_id": _prompt("  Staff (code / username): "),
                         **ask_fields(_TRAINING)}, actor=p)
    print(f"  ✓ Recorded; expires {t.expires_on or 'never'}")


def _edit_training(p: Principal) -> None:
    tid = _int("  Training #: ")
    if tid:
        t = CP.get_training(tid)
        CP.update_training(tid, ask_fields(_TRAINING, t), actor=p)
        print("  ✓ Saved.")


def _delete_training(p: Principal) -> None:
    tid = _int("  Training #: ")
    if tid and _yes("  Delete this training record?"):
        CP.delete_training(tid, actor=p)
        print("  ✓ Deleted.")


def _export(p: Principal) -> None:
    what = prompts.pick("Export", ("appraisals", "cpd", "training"), "appraisals")
    path = _prompt("  Save CSV to: ")
    if path:
        print(f"  Exported {CP.export_csv(path, what or 'appraisals', actor=p)} row(s).")


# ── The old CPD menu ─────────────────────────────────────────────────

def _activities(rows: list[AP.Activity]) -> None:
    if not rows:
        print("  (no activities)")
    for a in rows:
        print(f"    #{a.activity_id:<4} {a.activity_date} {a.activity_type[:16]:<16} "
              f"{a.title[:30]:<30} {(a.provider or '')[:16]:<16} "
              f"{a.records:>3} booked  [{a.status}]")


def _records(rows: list[AP.Record]) -> None:
    if not rows:
        print("  (no records)")
    for r in rows:
        print(f"    #{r.record_id:<4} {r.staff_name[:20]:<20} {r.title[:28]:<28} "
              f"{r.start_date or '':<10} £{r.cost or 0:>8,.2f} {'cover ' if r.cover_needed else '':<6}"
              f"[{r.status}]" + (f" rated {r.evaluation_rating}" if r.evaluation_rating else ""))


def _activity() -> AP.Activity | None:
    aid = _int("  Activity #: ")
    return CP.get_activity(aid) if aid else None


def _record(p: Principal) -> AP.Record | None:
    rid = _int("  Record #: ")
    return CP.get_record(rid, actor=p) if rid else None


def _cpd_new_activity(p: Principal) -> None:
    a = CP.create_activity(ask_fields(_ACTIVITY), actor=p)
    print(f"  ✓ Activity #{a.activity_id}")


def _cpd_edit_activity(p: Principal) -> None:
    a = _activity()
    if a:
        CP.update_activity(a.activity_id, ask_fields(_ACTIVITY, a), actor=p)
        print("  ✓ Saved.")


def _cpd_activity_status(p: Principal) -> None:
    a = _activity()
    if a:
        CP.set_activity_status(a.activity_id, prompts.pick("Status", AP.ACTIVITY_STATUSES,
                                                           a.status) or a.status, actor=p)
        print("  ✓ Saved.")


def _cpd_delete_activity(p: Principal) -> None:
    a = _activity()
    if a and _yes(f"  Delete '{a.title}'? Its records are kept."):
        CP.delete_activity(a.activity_id, actor=p)
        print("  ✓ Deleted.")


def _cpd_mark_completed(p: Principal) -> None:
    a = _activity()
    if a:
        CP.mark_activity_completed(a.activity_id, actor=p)
        print("  ✓ Completed.")


def _cpd_filter_activities(_p: Principal) -> None:
    t = prompts.pick("Type (blank = all)", AP.ACTIVITY_TYPES)
    st = prompts.pick("Status (blank = all)", AP.ACTIVITY_STATUSES)
    _activities(CP.list_activities(activity_type=t or None, status=st or None,
                                   title=_prompt("  Title contains: ")))


def _cpd_filter_records(p: Principal) -> None:
    st = prompts.pick("Status (blank = all)", AP.RECORD_STATUSES)
    m = SD.find(_prompt("  Staff (blank = all): ") or None)
    _records(CP.list_records(actor=p, status=st or None, staff_id=m.staff_id if m else None))


def _cpd_per_staff(p: Principal) -> None:
    m = SD.find(_prompt("  Staff (code / username): "))
    if m:
        _records(CP.records_for_staff(m.staff_id, actor=p))


def _cpd_for_activity(p: Principal) -> None:
    a = _activity()
    if a:
        _records(CP.list_records(actor=p, activity_id=a.activity_id))


def _cpd_new_record(p: Principal) -> None:
    r = CP.create_record({"staff_id": _prompt("  Staff (code / username): "),
                          **ask_fields(_REQUEST),
                          "status": prompts.pick("Status", AP.RECORD_STATUSES,
                                                 AP.DEFAULT_RECORD_STATUS)}, actor=p)
    print(f"  ✓ Record #{r.record_id} ({r.status})")


def _cpd_edit_record(p: Principal) -> None:
    r = _record(p)
    if r:
        CP.update_record(r.record_id, ask_fields(_REQUEST, r), actor=p)
        print("  ✓ Saved.")


def _cpd_attended(p: Principal) -> None:
    r = _record(p)
    if r:
        CP.mark_attended(r.record_id, actor=p,
                         attended_on=_prompt("  Attended on (blank = today): ") or None,
                         hours_completed=_prompt("  Hours completed: ") or None)
        print("  ✓ Attended.")


def _cpd_evaluate(p: Principal) -> None:
    r = _record(p)
    if r:
        CP.record_evaluation(r.record_id, actor=p, rating=_prompt("  Rating (1-5): "),
                             notes=_prompt("  Notes: ") or None,
                             impact=_prompt("  Impact on practice: ") or None)
        print("  ✓ Evaluated.")


def _cpd_certificate(p: Principal) -> None:
    r = _record(p)
    if r:
        CP.file_certificate(r.record_id, actor=p, ref=_prompt("  Certificate ref: ") or None)
        print("  ✓ Filed.")


def _cpd_record_status(p: Principal) -> None:
    r = _record(p)
    if r:
        CP.set_record_status(r.record_id, prompts.pick("Status", AP.RECORD_STATUSES, r.status)
                             or r.status, actor=p)
        print("  ✓ Saved.")


def _cpd_delete_record(p: Principal) -> None:
    r = _record(p)
    if r and _yes(f"  Delete record #{r.record_id}?"):
        CP.delete_record(r.record_id, actor=p)
        print("  ✓ Deleted.")


def _cpd_request(p: Principal) -> None:
    data = ask_fields(_REQUEST)
    if AP.is_editor(p):
        who = _prompt("  For (staff code, blank = you): ")
        if who:
            data["staff_id"] = who
    r = CP.request_cpd(data, actor=p)
    print(f"  ✓ Request #{r.record_id} sent to the CPD lead.")


def _cpd_decide(p: Principal) -> None:
    r = _record(p)
    if r is None:
        return
    approve = _yes(f"  Approve '{r.title}' for {r.staff_name} (£{r.cost or 0:,.2f})? "
                   "(No = decline)")
    note = _prompt("  Note" + ("" if approve else " (why)") + ": ") or None
    try:
        CP.decide(r.record_id, approve, actor=p, note=note)
    except AP.ValidationError as e:
        if not (approve and "over" in str(e)):
            raise
        print(f"  ! {e}")
        if not _yes("  Approve anyway?"):
            return
        CP.decide(r.record_id, True, actor=p, note=note, allow_over_budget=True)
    print("  ✓ Decided.")


def _cpd_withdraw(p: Principal) -> None:
    r = _record(p)
    if r and _yes(f"  Withdraw '{r.title}'?"):
        CP.withdraw_request(r.record_id, actor=p)
        print("  ✓ Withdrawn.")


def _cpd_log(p: Principal) -> None:
    ref = _prompt("  Staff (blank = you): ")
    m = SD.find(ref) if ref else SD.me(p)
    if m is None:
        print("  ✗ No staff record")
        return
    log = CP.cpd_log(m.staff_id, actor=p)
    print(f"\n  {m.full_name}: {log['hours']:g} hour(s) of CPD")
    for y, d in sorted(log["by_year"].items(), reverse=True):
        print(f"    {y}: {d['courses']} course(s), {d['hours']:g} h, £{d['cost']:,.2f}")
    _records(log["records"])


def _cpd_budget(_p: Principal) -> None:
    b = CP.budget(_prompt(f"  Academic year [{AP.current_year()}]: ") or None)
    if b["available"] is None:
        print(f"  No budget set for {b['year']}; £{b['used']:,.2f} approved so far.")
    else:
        print(f"  {b['year']}: £{b['available']:,.2f} available, £{b['used']:,.2f} used, "
              f"£{b['remaining']:,.2f} left, £{b['requested']:,.2f} waiting for a decision")


def _cpd_set_budget(p: Principal) -> None:
    b = CP.set_budget(_prompt(f"  Academic year [{AP.current_year()}]: ") or None,
                      _prompt("  Budget (£): "), actor=p)
    print(f"  ✓ {b['year']} budget £{b['available']:,.2f}")


def _cpd_export(p: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. cpd.csv): ")
    if path:
        print(f"  Exported {CP.export_csv(path, 'cpd', actor=p)} record(s).")


_CPD: dict[str, Callable[[Principal], None]] = {
    "2": lambda p: _activities(CP.list_activities()),
    "3": lambda p: _activities(CP.list_activities(upcoming_only=True)),
    "4": lambda p: _activities(CP.list_activities(completed_only=True)),
    "5": _cpd_filter_activities, "6": _cpd_new_activity, "7": _cpd_edit_activity,
    "8": _cpd_mark_completed, "9": _cpd_activity_status, "10": _cpd_delete_activity,
    "12": lambda p: _records(CP.list_records(actor=p)),
    "13": lambda p: _records(CP.list_records(actor=p, awaiting_cert=True)),
    "14": lambda p: _records(CP.list_records(actor=p, completed_only=True)),
    "15": _cpd_per_staff, "16": _cpd_for_activity, "17": _cpd_filter_records,
    "18": _cpd_new_record, "19": _cpd_edit_record, "20": _cpd_attended, "21": _cpd_evaluate,
    "22": _cpd_certificate, "23": _cpd_record_status, "24": _cpd_delete_record,
    "26": _summary, "27": _cpd_request, "28": _cpd_decide, "29": _cpd_withdraw,
    "30": _cpd_log, "31": _cpd_budget, "32": _cpd_set_budget, "33": _cpd_export}


def _loop(title: str, text: str, options: dict[str, Callable[[Principal], None]],
          principal: Principal) -> None:
    while True:
        activity_log.record("appraisals.view")
        print(f"\n── {title} ──")
        print(text)
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        fn = options.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            prompts.problem(e)
        except OSError as e:
            print(f"\n  ✗ {e}")
        _pause()


def _cpd_menu(principal: Principal) -> None:
    _loop("CPD", "      ── Activities ──\n   2) List all\n   3) Upcoming\n   4) Completed"
                 "\n   5) Filter\n   6) New activity\n   7) Edit activity\n   8) Mark completed"
                 "\n   9) Change status\n  10) Delete activity\n      ── Records ──"
                 "\n  12) List all\n  13) Awaiting certificate\n  14) Completed\n  15) Per-staff"
                 "\n  16) For activity\n  17) Filter\n  18) New record\n  19) Edit record"
                 "\n  20) Mark attended\n  21) Record evaluation\n  22) File certificate"
                 "\n  23) Change status\n  24) Delete record\n      ──\n  26) Summary"
                 "\n  More\n  27) Request training\n  28) Approve / decline a request"
                 "\n  29) Withdraw\n  30) CPD log\n  31) Budget\n  32) Set the budget"
                 "\n  33) Export CSV", _CPD, principal)


_OPTIONS: dict[str, Callable[[Principal], None]] = {
    "2": _list, "3": _open, "4": _overdue, "5": _filter, "6": _per_staff, "7": _view,
    "8": _new, "9": _edit, "10": _set_objectives, "11": _mid_year, "12": _end_year,
    "13": _close, "14": _status, "15": _delete, "17": _objectives, "18": _add_objective,
    "19": _edit_objective, "20": _objective_status, "21": _delete_objective, "23": _summary,
    "24": _cpd_menu, "25": _start_cycle, "26": _observations, "27": _new_observation,
    "28": _edit_observation, "29": _respond, "30": _delete_observation, "31": _training,
    "32": _due, "33": _add_training, "34": _edit_training, "35": _delete_training,
    "36": _export}


def menu(principal: Principal) -> None:
    _loop("Appraisals & CPD",
          "      ── Appraisals ──\n   2) List all\n   3) Open only\n   4) Mid-year overdue"
          "\n   5) Filter\n   6) Per-staff\n   7) View\n   8) New appraisal\n   9) Edit appraisal"
          "\n  10) Mark objectives set\n  11) Record mid-year\n  12) Record end-year"
          "\n  13) Close appraisal\n  14) Change status\n  15) Delete appraisal"
          "\n      ── Objectives ──\n  17) List objectives\n  18) Add objective"
          "\n  19) Edit objective\n  20) Change objective status\n  21) Delete objective"
          "\n      ──\n  23) Summary"
          "\n  More\n  24) CPD (activities, records, requests, budget)\n  25) Start the cycle"
          "\n  26) Observations\n  27) New observation\n  28) Edit observation"
          "\n  29) Respond to an observation\n  30) Delete observation"
          "\n  31) Statutory training\n  32) Training due / overdue\n  33) Record training"
          "\n  34) Edit training\n  35) Delete training\n  36) Export CSV", _OPTIONS, principal)
