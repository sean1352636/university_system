"""Safeguarding in the terminal (the DSL and deputies).

The old menu keeps its options in place: 1 Raise concern, 2 List concerns,
3 View concern + actions, 4 Edit concern, 5 Set status, 6 Pupils with open
concerns, 7 Delete concern, 8 Add action, 9 Delete action, 10 Cohort summary.
New: 11 Triage new reports, 12 Due, 13 Complete an action, 14 Add referral,
15 Referral outcome, 16 Referrals waiting, 17 Close concern, 18 Reopen
concern, 19 Plans, 20 Pupil chronology, 21 Transfer file, 22 Record transfer,
23 Leavers to transfer, 24 Prevent (the old Prevent Duty menu, its options in
place), 25 Access log, 26 Safeguarding team, 27 Reports, 28 History,
29 Export CSV. Rules: :mod:`modules.safeguarding.domain.safeguarding`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.safeguarding.domain import safeguarding as SG
from education_system.systems.secondary.modules.safeguarding.domain import (
    safeguarding_records as SR,
)
from education_system.systems.secondary.modules.safeguarding.domain import (
    safeguarding_reports as SGR,
)
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (SG.ValidationError, SG.PermissionDenied, SG.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _table(rows: list[SG.Concern]) -> None:
    if not rows:
        print("  (no concerns)")
        return
    print(f"  {'ID':<4} {'Raised':<10} {'Pupil':<24} {'Yr':<3} {'Category':<22} {'Sev':<9} "
          f"{'Status':<11} {'DSL':<14} {'Conf':<4} !")
    for c in rows:
        print(f"  {c.concern_id:<4} {c.raised_date:<10} {c.pupil_name[:24]:<24} "
              f"{c.pupil_year:<3} {c.category[:22]:<22} {c.severity:<9} {c.status:<11} "
              f"{(c.dsl_reviewer or '-')[:14]:<14} {('Y' if c.confidential else 'N'):<4} "
              f"{'!' if c.urgent else ''}")


def _ask(label: str, cur: Any) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _concern(principal: Principal) -> SG.Concern | None:
    cid = _int("  Concern ID: ")
    return SG.get(cid, actor=principal, log=False) if cid else None


def _collect(existing: SG.Concern | None = None) -> dict[str, Any]:
    """The old questions in their order; Enter keeps the current value."""
    f: dict[str, Any] = {}
    if existing is None:
        f["pupil_id"] = _prompt("  Pupil ID / admission no.: ")
    cat = _pick("Category", SG.CONCERN_CATEGORIES,
                existing.category if existing else SG.DEFAULT_CATEGORY)
    if cat:
        f["category"] = cat
    sev = _pick("Severity", SG.SEVERITIES, existing.severity if existing
                else SG.DEFAULT_SEVERITY)
    if sev:
        f["severity"] = sev
    for key, label in (("incident_date", "Incident date (YYYY-MM-DD, blank ok)"),
                       ("incident_time", "Incident time (HH:MM, blank ok)"),
                       ("location", "Location"), ("description", "Description (required)"),
                       ("raised_by", "Raised by"),
                       ("raised_date", "Raised date (YYYY-MM-DD, blank = today)"),
                       ("dsl_reviewer", "DSL reviewer"),
                       ("review_date", "DSL review date (blank ok)")):
        v = _ask(label, getattr(existing, key) if existing else None)
        if v:
            f[key] = v
    st = _pick("Status", SG.CONCERN_STATUSES, existing.status if existing else
               SG.DEFAULT_STATUS)
    if st:
        f["status"] = st
    body = _pick("Referral body (blank ok)", SG.REFERRAL_BODIES,
                 existing.referral_body if existing else None)
    if body:
        f["referral_body"] = body
    for key, label in (("referral_date", "Referral date (blank ok)"),
                       ("referral_reference", "Referral reference (blank ok)"),
                       ("outcome", "Outcome"), ("closed_date", "Closed date (blank ok)")):
        v = _ask(label, getattr(existing, key) if existing else None)
        if v:
            f[key] = v
    conf = _ask("Confidential? (y/n)", "y" if existing is None or existing.confidential
                else "n")
    if conf:
        f["confidential"] = conf.lower().startswith("y")
    for key, label in (("notes", "Notes"), ("child_words", "Child's own words"),
                       ("body_map", "Injury / body map"),
                       ("immediate_action", "Immediate action taken"),
                       ("people_involved", "Others involved"),
                       ("allegation_about", "Allegation about (LADO, blank ok)")):
        v = _ask(label, getattr(existing, key) if existing else None)
        if v:
            f[key] = v
    lvl = _pick("Level of need (blank ok)", SG.LEVELS,
                existing.level_of_need if existing else None)
    if lvl:
        f["level_of_need"] = lvl
    return f


def _new(principal: Principal) -> None:
    print("\n  ── Raise Safeguarding Concern ──")
    c = SG.raise_concern(_collect(), actor=principal)
    print(f"  Raised concern #{c.concern_id}: {c.category} ({c.severity}, {c.status})")


def _list(principal: Principal) -> None:
    pid = _prompt("  Pupil ID / admission no. (blank): ")
    p = SG._pupil(pid) if pid else None
    if pid and p is None:
        print("  No such pupil.")
        return
    year = _prompt("  Year (blank): ")
    cat = _pick("Category (blank)", SG.CONCERN_CATEGORIES)
    sev = _pick("Severity (blank)", SG.SEVERITIES)
    status = _pick("Status (blank)", SG.CONCERN_STATUSES)
    df = _prompt("  From date (blank): ")
    dt = _prompt("  To date (blank): ")
    show = _yes("  Show description?")
    rows = SG.list_concerns(actor=principal, pupil_id=p.pupil_id if p else None,
                            year_group=year or None, category=cat or None,
                            severity=sev or None, status=status or None,
                            date_from=df or None, date_to=dt or None)
    print(f"\n  {len(rows)} concern(s):")
    _table(rows)
    if show:
        for c in rows:
            SG.log_access(principal, "concern", pupil_id=c.pupil_id, concern_id=c.concern_id)
            print(f"  #{c.concern_id}: {c.description[:100]}")


def _print_actions(rows: list[SG.SGAction]) -> None:
    if not rows:
        print("  (no actions)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Type':<22} {'By':<16} {'Due':<10} {'Done':<10} Summary")
    for a in rows:
        print(f"  {a.action_id:<5} {a.action_date:<10} {a.action_type[:22]:<22} "
              f"{(a.actioned_by or '-')[:16]:<16} {(a.due_date or ''):<10} "
              f"{(a.completed_date or ''):<10} {a.summary[:40]}")


def _view(principal: Principal) -> None:
    cid = _int("  Concern ID: ")
    if not cid:
        return
    s = SGR.concern_summary(cid, actor=principal)
    c = s["concern"]
    print(f"\n  ── Concern #{c.concern_id} ──")
    for label, v in (("Pupil", f"{c.pupil_name} ({c.admission_no}), Yr {c.pupil_year}"),
                     ("Category", f"{c.category}    Severity: {c.severity}"
                                  + ("    URGENT" if c.urgent else "")),
                     ("Level", c.level_of_need),
                     ("Incident", f"{c.incident_date or '-'} {c.incident_time or ''}    "
                                  f"Location: {c.location or '-'}"),
                     ("Raised by", f"{c.raised_by or '-'} on {c.raised_date}"),
                     ("DSL", f"{c.dsl_reviewer or '-'}    review {c.review_date or '-'}"),
                     ("Status", c.status),
                     ("Referral", f"{c.referral_body or '-'}    on {c.referral_date or '-'}"
                                  f"    ref: {c.referral_reference or '-'}"),
                     ("Allegation about", c.allegation_about),
                     ("Outcome", c.outcome or "-"), ("Closed", c.closed_date or "-"),
                     ("Confidential", "Yes" if c.confidential else "No")):
        if v:
            print(f"  {label + ':':<17} {v}")
    for label, v in (("Description", c.description), ("Child's words", c.child_words),
                     ("Injury / body map", c.body_map), ("Immediate action", c.immediate_action),
                     ("Others involved", c.people_involved), ("Notes", c.notes or "-")):
        if v:
            print(f"\n  {label}:\n    {v}")
    print(f"\n  Actions: {s['action_count']}")
    for k, v in s["by_type"].items():
        print(f"    {k:<26} {v}")
    _print_actions(s["actions"])
    for r in s["referrals"]:
        print(f"  Referral #{r.referral_id}: {r.referral_date} {r.agency} "
              f"{r.reference or ''} - {r.outcome}")


def _edit(principal: Principal) -> None:
    c = _concern(principal)
    if c is None:
        return
    c = SG.get(c.concern_id, actor=principal)
    print("  Press Enter to keep existing value.")
    changes = _collect(c)
    changes = {k: v for k, v in changes.items() if str(v) != str(getattr(c, k, None) or "")}
    if not changes:
        print("  Nothing changed.")
        return
    c = SG.update(c.concern_id, changes, actor=principal)
    print(f"  Updated concern #{c.concern_id} (status {c.status})")


def _set_status(principal: Principal) -> None:
    c = _concern(principal)
    if c is None:
        return
    new = _pick("New status", SG.CONCERN_STATUSES, c.status)
    outcome = _ask("Outcome", c.outcome) if new == "Closed" else None
    body = _pick("Referral body", SG.REFERRAL_BODIES, c.referral_body) \
        if new == "Referred" else None
    c = SG.set_status(c.concern_id, new or c.status, actor=principal, outcome=outcome,
                      referral_body=body)
    print(f"  Status now: {c.status}")


def _at_risk(principal: Principal) -> None:
    sev = _pick("Minimum severity", SG.SEVERITIES, "High") or "High"
    pupils = SGR.pupils_with_concerns(actor=principal, severity_min=sev)
    print(f"\n  {len(pupils)} pupil(s) with open concerns ≥ {sev}:")
    for concerns in pupils.values():
        print(f"\n  {concerns[0].pupil_name} ({concerns[0].admission_no}) — "
              f"{len(concerns)} concern(s):")
        for c in concerns:
            print(f"    #{c.concern_id:<5} {c.severity:<8} {c.category[:24]:<24} {c.status}")


def _delete(principal: Principal) -> None:
    c = _concern(principal)
    if c and _yes(f"  Delete concern #{c.concern_id} ({c.pupil_name}, {c.category}) and ALL "
                  "its actions?"):
        SG.delete(c.concern_id, actor=principal, reason=_prompt("  Why (logged in error?): "))
        print(f"  Deleted concern #{c.concern_id}.")


def _add_action(principal: Principal) -> None:
    c = _concern(principal)
    if c is None:
        return
    f: dict[str, Any] = {"concern_id": c.concern_id,
                         "action_date": _prompt("  Action date (YYYY-MM-DD, blank = today): "),
                         "action_type": _pick("Type", SG.ACTION_TYPES, SG.DEFAULT_ACTION_TYPE),
                         "actioned_by": _prompt("  Actioned by: "),
                         "summary": _prompt("  Summary: "), "outcome": _prompt("  Outcome: "),
                         "follow_up": _prompt("  Follow-up: "),
                         "due_date": _prompt("  Due date for a follow-up (blank ok): "),
                         "assigned_to": _prompt("  Who will do it (blank ok): ")}
    a = SG.add_action(f, actor=principal)
    print(f"  Added action #{a.action_id} ({a.action_type})")


def _delete_action(principal: Principal) -> None:
    aid = _int("  Action ID: ")
    if aid and _yes(f"  Delete action #{aid}?"):
        SG.delete_action(aid, actor=principal)
        print(f"  Deleted action #{aid}.")


def _summary(principal: Principal) -> None:
    yg = _prompt("  Year (blank): ")
    df = _prompt("  From date (blank): ")
    dt = _prompt("  To date (blank): ")
    s = SGR.cohort_summary(actor=principal, year_group=yg or None, date_from=df or None,
                           date_to=dt or None)
    print(f"\n  Concerns: {s['total']}    Open: {s['open']}    Open Critical: "
          f"{s['open_critical']}    New: {s['new']}    Urgent open: {s['urgent_open']}")
    for key in ("by_severity", "by_status", "by_level"):
        if s[key]:
            print(f"  {key[3:].title() + ':':<12} " + "   ".join(f"{k}: {v}"
                                                               for k, v in s[key].items()))
    print("  By category:")
    for k, v in sorted(s["by_category"].items(), key=lambda kv: -kv[1]):
        print(f"    {k:<34} {v}")


def _triage(principal: Principal) -> None:
    rows = SG.awaiting_triage(actor=principal)
    print(f"\n  {len(rows)} new report(s):")
    _table(rows)
    c = _concern(principal)
    if c is None:
        return
    c = SG.get(c.concern_id, actor=principal)
    print(f"\n  {c.description}\n  Child's words: {c.child_words or '-'}")
    lvl = _pick("Level of need / action", SG.LEVELS)
    about = _prompt("  Allegation about (LADO only): ") if lvl == SG.LADO_LEVEL else None
    c = SG.triage(c.concern_id, actor=principal, level=lvl or "",
                  severity=_pick("Severity", SG.SEVERITIES, c.severity),
                  category=_pick("Category", SG.CONCERN_CATEGORIES, c.category),
                  note=_prompt("  Decision / rationale: "), allegation_about=about)
    print(f"  Triaged: {c.level_of_need}, status {c.status}.")


def _due(principal: Principal) -> None:
    rows = SGR.due(actor=principal)
    if not rows:
        print("  Nothing due.")
    for d in rows:
        print(f"  {d['due'] or '':<10} {'OVERDUE' if d['overdue'] else '':<8} "
              f"{d['kind']:<14} #{d['concern_id']:<4} {d['pupil'][:26]:<26} {d['what'][:60]}"
              + (f"  [action {d['action_id']}]" if d["action_id"] else ""))
    for x in SR.plan_reviews_due(actor=principal):
        print(f"  {x.next_review:<10} {'':<8} {'Plan review':<14} {'':<5} "
              f"{x.pupil_name[:26]:<26} {x.plan_type}")


def _complete(principal: Principal) -> None:
    aid = _int("  Action ID: ")
    if aid:
        SG.complete_action(aid, actor=principal, outcome=_prompt("  Outcome (blank ok): "))
        print("  Done.")


def _add_referral(principal: Principal) -> None:
    c = _concern(principal)
    if c is None:
        return
    r = SG.add_referral(c.concern_id, {
        "agency": _pick("Referred to", SG.REFERRAL_BODIES),
        "referral_date": _prompt("  Date (blank = today): "),
        "reference": _prompt("  Their reference: "),
        "allegation_about": c.allegation_about or _prompt("  Allegation about (LADO only): "),
        "reason": _prompt("  Reason / what was shared: ")}, actor=principal)
    print(f"  Referral #{r.referral_id} recorded.")


def _referral_outcome(principal: Principal) -> None:
    rid = _int("  Referral ID: ")
    if not rid:
        return
    r = SG.record_referral_outcome(rid, actor=principal, outcome=_pick(
        "Outcome", [o for o in SG.REFERRAL_OUTCOMES if o != "Pending"]) or "",
        day=_prompt("  Date (blank = today): ") or None, notes=_prompt("  Notes: "))
    print(f"  {r.agency}: {r.outcome}.")


def _referrals(principal: Principal) -> None:
    rows = SG.list_referrals(actor=principal, pending_only=_yes("  Waiting for an outcome only?"))
    if not rows:
        print("  (no referrals)")
    for r in rows:
        print(f"  #{r.referral_id:<4} {r.referral_date} concern #{r.concern_id:<4} "
              f"{r.pupil_name[:24]:<24} {r.agency:<20} {r.reference or '':<10} {r.outcome}")


def _close(principal: Principal) -> None:
    c = _concern(principal)
    if c:
        c = SG.close_concern(c.concern_id, actor=principal, outcome=_prompt("  Outcome: "))
        print(f"  Closed on {c.closed_date}.")


def _reopen(principal: Principal) -> None:
    c = _concern(principal)
    if c:
        SG.reopen(c.concern_id, actor=principal, reason=_prompt("  Why: "))
        print("  Reopened.")


def _pupil(principal: Principal):
    p = SG._pupil(_prompt("  Pupil ID / admission no.: "))
    if p is None:
        print("  No such pupil.")
    return p


def _plans(principal: Principal) -> None:
    p = _pupil(principal)
    if p is None:
        return
    f = SR.flags(p.pupil_id, actor=principal)
    print(f"\n  {p.display_name}: " + (", ".join(f["labels"]) or "nothing current"))
    for x in SR.list_plans(actor=principal, pupil_id=p.pupil_id):
        print(f"  #{x.plan_id:<4} {x.plan_type:<24} {x.category or '':<16} {x.start_date} to "
              f"{x.end_date or 'now':<10} {x.local_authority or ''} {x.social_worker or ''}")
    choice = _prompt("  a) Add plan  e) End plan  Enter) Back: ").lower()
    if choice == "a":
        data = {"pupil_id": p.pupil_id, "plan_type": _pick("Plan", SR.PLAN_TYPES)}
        if data["plan_type"] == SR.CP:
            data["category"] = _pick("Category", SR.CP_CATEGORIES)
        for key, label in (("start_date", "Start date"), ("local_authority", "Local authority"),
                           ("social_worker", "Social worker"), ("contact", "Their phone/e-mail"),
                           ("next_review", "Next review (blank ok)"), ("notes", "Notes")):
            data[key] = _prompt(f"  {label}: ")
        x = SR.add_plan(data, actor=principal)
        print(f"  Plan #{x.plan_id} added.")
    elif choice == "e":
        pid = _int("  Plan ID: ")
        if pid:
            SR.end_plan(pid, actor=principal, end_date=_prompt("  End date (blank = today): ")
                        or None, note=_prompt("  Why / next step: "))
            print("  Ended.")


def _chronology(principal: Principal) -> None:
    p = _pupil(principal)
    if p:
        print("\n" + SR.chronology_text(p.pupil_id, actor=principal))


def _transfer_file(principal: Principal) -> None:
    p = _pupil(principal)
    if p is None:
        return
    text = SR.transfer_file(p.pupil_id, actor=principal)
    path = _prompt("  Save to file (blank = show here): ")
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"  Saved to {path}. Send it securely, then use option 22.")
    else:
        print("\n" + text)


def _record_transfer(principal: Principal) -> None:
    p = _pupil(principal)
    if p is None:
        return
    t = SR.record_transfer(p.pupil_id, {
        "destination": _prompt("  Sent to (blank = the leaving record's school): "),
        "method": _pick("How", SR.TRANSFER_METHODS, SR.TRANSFER_METHODS[0]),
        "sent_date": _prompt("  Sent on (blank = today): "),
        "notes": _prompt("  Notes: ")}, actor=principal)
    print(f"  Transfer #{t.transfer_id} recorded; open concerns marked Transferred.")
    if _yes("  Has the new school confirmed receipt?"):
        SR.receipt_confirmed(t.transfer_id, actor=principal,
                             received_by=_prompt("  Confirmed by: "))
        print("  Receipt recorded.")


def _leavers(principal: Principal) -> None:
    rows = SR.leavers_to_transfer(actor=principal)
    if not rows:
        print("  No leavers waiting for their file to be sent.")
    for x in rows:
        p = x["pupil"]
        print(f"  {p.display_name[:26]:<26} ({p.admission_no}) left {x['leaving_date']} to "
              f"{x['destination'] or '?':<20} send by {x['due']}"
              + ("  OVERDUE" if x["overdue"] else ""))
    sent = SR.list_transfers(actor=principal)
    if sent:
        print("\n  Sent:")
    for t in sent:
        print(f"  #{t.transfer_id:<4} {t.sent_date} {t.pupil_name[:24]:<24} to {t.destination} "
              f"({t.method})" + (f" - received {t.received_date}" if t.received_date
                                 else " - not confirmed"))


# ── Prevent (the old Prevent Duty menu) ─────────────────────────────

def _pv_collect(cur: SR.Prevent | None = None) -> dict[str, Any]:
    f: dict[str, Any] = {}
    if cur is None:
        f["pupil_id"] = _prompt("  Pupil ID / admission no.: ")
    f["prevent_type"] = _pick("Concern type", SR.PREVENT_TYPES,
                              cur.prevent_type if cur else SR.DEFAULT_PREVENT_TYPE)
    f["risk_level"] = _pick("Risk level", SR.RISK_LEVELS, cur.risk_level if cur
                            else SR.DEFAULT_RISK)
    if cur is None:
        for key, label in (("raised_by", "Raised by"), ("description", "Description"),
                           ("dsl_name", "DSL informed (name)"),
                           ("dsl_informed_date", "DSL informed date")):
            f[key] = _prompt(f"  {label}: ")
    for key, label in (("indicators", "Indicators"), ("online_activity", "Online activity")):
        v = _ask(label, getattr(cur, key) if cur else None)
        if v:
            f[key] = v
    f["pathway"] = _pick("Referral pathway", SR.PATHWAYS, cur.pathway if cur
                         else SR.DEFAULT_PATHWAY)
    if cur is None:
        f["referral_date"] = _prompt("  Referral date (blank ok): ")
        f["referral_ref"] = _prompt("  Referral ref (blank ok): ")
    for key, label in (("agencies_involved", "Agencies involved"),
                       ("parents_informed_date", "Parents informed date (blank ok)"),
                       ("next_review_date", "Next review date (blank ok)")):
        v = _ask(label, getattr(cur, key) if cur else None)
        if v:
            f[key] = v
    if cur is not None:
        f["channel_status"] = _pick("Status", SR.PREVENT_STATUSES, cur.channel_status)
        f["prevent_outcome"] = _pick("Outcome", SR.PREVENT_OUTCOMES, cur.prevent_outcome)
    return {k: v for k, v in f.items() if v not in (None, "")}


def _pv_print(rows: list[SR.Prevent]) -> None:
    if not rows:
        print("  (no referrals)")
    for x in rows:
        c = x.concern
        print(f"  {c.concern_id:<5} {c.pupil_name[:20]:<20} {c.pupil_year:<3} {c.raised_date:<11}"
              f" {x.prevent_type[:22]:<22} {x.risk_level:<9} {x.pathway[:22]:<22} "
              f"{x.channel_status}")


def _prevent(principal: Principal) -> None:
    while True:
        print("\n  ── Prevent Duty ──")
        print("   1) New referral\n   2) List referrals\n   3) View referral\n"
              "   4) Edit referral\n   5) Set status\n   6) Close referral\n"
              "   7) Cohort summary\n   8) Delete referral\n   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        try:
            if choice == "1":
                x = SR.create_prevent(_pv_collect(), actor=principal)
                print(f"  Created referral #{x.concern.concern_id}: {x.concern.pupil_name} — "
                      f"{x.prevent_type}")
            elif choice == "2":
                _pv_print(SR.list_prevent(
                    actor=principal, status=_pick("Status (blank)", SR.PREVENT_STATUSES),
                    risk_level=_pick("Risk (blank)", SR.RISK_LEVELS),
                    open_only=_yes("  Open only?")))
            elif choice in ("3", "4", "5", "6", "8"):
                rid = _int("  Referral ID: ")
                if not rid:
                    continue
                x = SR.get_prevent(rid, actor=principal)
                c = x.concern
                if choice == "3":
                    for label, v in (("Pupil", f"{c.pupil_name} ({c.admission_no})"),
                                     ("Concern", x.prevent_type), ("Risk", x.risk_level),
                                     ("Raised by", f"{c.raised_by} on {c.raised_date}"),
                                     ("DSL", f"{c.dsl_reviewer or '-'} {c.review_date or ''}"),
                                     ("Description", c.description),
                                     ("Indicators", x.indicators or "-"),
                                     ("Online", x.online_activity or "-"),
                                     ("Pathway", f"{x.pathway}    {c.referral_date or ''} "
                                                 f"{c.referral_reference or ''}"),
                                     ("Agencies", x.agencies_involved or "-"),
                                     ("Parents", x.parents_informed_date or "not informed"),
                                     ("Next review", x.next_review_date or "-"),
                                     ("Status", f"{x.channel_status}    Outcome: "
                                                f"{x.prevent_outcome}"),
                                     ("Closed", c.closed_date or "-"),
                                     ("Closure note", x.closure_notes or "-")):
                        print(f"  {label + ':':<13} {v}")
                elif choice == "4":
                    SR.update_prevent(rid, _pv_collect(x), actor=principal)
                    print("  Saved.")
                elif choice == "5":
                    st = _pick("Status", SR.PREVENT_STATUSES, x.channel_status)
                    SR.update_prevent(rid, {"channel_status": st}, actor=principal)
                    print(f"  Status now: {st}")
                elif choice == "6":
                    SR.close_prevent(rid, actor=principal, status=_pick(
                        "Closed status", [s for s in SR.PREVENT_STATUSES
                                          if s.startswith("Closed")],
                        "Closed — no further action") or "Closed — no further action",
                        outcome=_pick("Outcome", SR.PREVENT_OUTCOMES, "No further action")
                        or "No further action", notes=_prompt("  Closure notes: "))
                    print("  Closed.")
                elif _yes(f"  Delete referral #{rid}?"):
                    SG.delete(rid, actor=principal, reason=_prompt("  Why: "))
                    print("  Deleted.")
            elif choice == "7":
                s = SR.prevent_summary(actor=principal)
                print(f"\n  Referrals: {s['total']}    Open: {s['open']}    Channel: "
                      f"{s['channel']}")
                for key in ("by_status", "by_risk", "by_type", "by_pathway"):
                    print(f"  {key[3:].title()}: " + ", ".join(f"{k} {v}"
                                                               for k, v in s[key].items()))
            else:
                print("  Invalid selection.")
        except _ERRORS as e:
            _problem(e)
        _pause()


def _access(principal: Principal) -> None:
    ref = _prompt("  Pupil ID / admission no. (blank = all): ")
    p = SG._pupil(ref) if ref else None
    for a in SG.access_log(actor=principal, pupil_id=p.pupil_id if p else None,
                           username=_prompt("  User (blank = all): ") or None, limit=200):
        print(f"  {a['at']}  {a['username']:<12} {a['role'] or '':<8} {a['pupil'][:30]:<30} "
              f"{a['concern_id'] or '':<5} {a['what']}")


def _team(principal: Principal) -> None:
    for m in SG.team():
        print(f"  {m['name']:<24} {m['team_role']:<20} {m['phone']:<16} "
              f"{m['email'] or '(no e-mail)'}" + ("" if m["listed"] else "  (by role)"))
    choice = _prompt("  a) Add / change  r) Remove  Enter) Back: ").lower()
    if choice == "a":
        SG.set_team_member(_prompt("  Staff login: "), {
            "team_role": _pick("Role", SG.TEAM_ROLES, "Deputy DSL"),
            "phone": _prompt("  Phone: "), "email": _prompt("  E-mail (blank = the login's): ")},
            actor=principal)
        print("  Saved.")
    elif choice == "r":
        SG.remove_team_member(_prompt("  Staff login: "), actor=principal)
        print("  Removed.")


def _reports(principal: Principal) -> None:
    by = _pick("Group by", ("category", "level", "year", "severity", "status", "month"),
               "category") or "category"
    print(f"\n  {'Group':<44} {'Concerns':>8} {'Open':>6} {'Pupils':>7} {'Referred':>9}")
    for g in SGR.analysis(actor=principal, by=by):
        print(f"  {g['group'][:44]:<44} {g['concerns']:>8} {g['open']:>6} {g['pupils']:>7} "
              f"{g['referred']:>9}")


def _history(principal: Principal) -> None:
    cid = _int("  Concern ID (blank = all): ")
    for h in SG.history(cid, actor=principal):
        print(f"  {h['at']}  {h['actor']:<12} {h['action']:<16} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. safeguarding.csv): ")
    if path:
        print(f"  Exported {SGR.export_csv(path, actor=principal)} concern(s) "
              "(no descriptions or notes).")


_OPTIONS = {"1": _new, "2": _list, "3": _view, "4": _edit, "5": _set_status, "6": _at_risk,
            "7": _delete, "8": _add_action, "9": _delete_action, "10": _summary,
            "11": _triage, "12": _due, "13": _complete, "14": _add_referral,
            "15": _referral_outcome, "16": _referrals, "17": _close, "18": _reopen,
            "19": _plans, "20": _chronology, "21": _transfer_file, "22": _record_transfer,
            "23": _leavers, "24": _prevent, "25": _access, "26": _team, "27": _reports,
            "28": _history, "29": _export}


def menu(principal: Principal) -> None:
    if not SG.is_lead(principal):
        print("\n  Safeguarding records are for the designated safeguarding lead and deputies."
              "\n  To pass on a concern, use Report a Safeguarding Concern.")
        activity_log.record("safeguarding.view", outcome="denied", principal=principal)
        _pause()
        return
    while True:
        activity_log.record("safeguarding.view")
        print("\n  ── Safeguarding ──")
        print("  Concerns\n    1) Raise concern\n    2) List concerns\n"
              "    3) View concern + actions\n    4) Edit concern\n    5) Set status\n"
              "    6) Pupils with open concerns (≥ High)\n    7) Delete concern")
        print("  Actions\n    8) Add action\n    9) Delete action")
        print("  Reports\n   10) Cohort summary")
        print("  More")
        print("   11) Triage new reports\n   12) Due\n   13) Complete an action"
              "\n   14) Add referral\n   15) Referral outcome\n   16) Referrals"
              "\n   17) Close concern\n   18) Reopen concern\n   19) Plans (CP / CIN / LAC)"
              "\n   20) Pupil chronology\n   21) Transfer file\n   22) Record transfer"
              "\n   23) Leavers to transfer\n   24) Prevent duty\n   25) Access log"
              "\n   26) Safeguarding team\n   27) Reports\n   28) History\n   29) Export CSV")
        print("    0) Back")
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
        if fn is not _prevent:
            _pause()
