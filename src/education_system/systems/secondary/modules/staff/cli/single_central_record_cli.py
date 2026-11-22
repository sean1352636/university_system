"""The single central record in the terminal.

The old DBS Checks menu keeps its numbers: 1 List all, 2 Active only,
3 Expired, 4 Expiring soon, 5 Update overdue, 6 Unsigned, 7 Risk assess.
pending, 8 Filter, 9 Per-staff, 10 View, 12 New check, 13 Edit check,
14 Issue certificate, 15 Mark certificate seen, 16 Subscribe to Update
Service, 17 Record update check, 18 Complete risk assessment, 19 Sign off,
20 Mark Lapsed, 21 Start renewal, 22 Change status, 23 Delete, 25 Summary
(11 and 24 were separators). New, after "More": 26 The record, 27 To do,
28 Reminders, 29 Add person, 30 Edit person, 31 Person's checks, 32 Add any
check, 33 Record leaving, 34 Delete person, 35 Add staff logins, 36 Sync
supply roster, 37 Print the record, 38 Export CSV, 39 History, 40 People not
on the record. Rules: :mod:`modules.staff.domain.single_central_record`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.staff.domain import single_central_record as SCR
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (SCR.ValidationError, SCR.PermissionDenied, SCR.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick
_MARK = {"ok": "ok", "missing": "MISSING", "pending": "pending", "expiring": "expiring",
         "expired": "EXPIRED", "overdue": "OVERDUE", "problem": "PROBLEM"}


def _checks_table(rows: list[SCR.Check]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print(f"\n  {'Id':<5} {'Staff':<20} {'Level':<26} {'DBS No':<13} {'Issued':<10} "
          f"{'Expires':<10} {'Cert':<18} {'US':<3} {'Signed':<12} Status")
    print("  " + "-" * 140)
    for c in rows:
        print(f"  {c.check_id:<5} {c.person_name[:20]:<20} {(c.dbs_level or c.check_type)[:26]:<26} "
              f"{c.dbs_number or c.reference or '':<13} {c.issued_on or '':<10} "
              f"{c.expires_on or '':<10} {(c.certificate_type or '')[:18]:<18} "
              f"{'Y' if c.update_service_subscribed else '':<3} "
              f"{(c.signed_off_by or '')[:12]:<12} {c.status}")
    print(f"\n  {len(rows)} check(s)")


def _dbs(principal: Principal, **filters: Any) -> None:
    _checks_table(SCR.list_checks(actor=principal, check_type=SCR.DBS, **filters))


def _person(principal: Principal) -> SCR.Person | None:
    text = _prompt("  Person (id, login or name): ")
    if not text:
        return None
    if text.isdigit():
        return SCR.get_person(int(text))
    rows = SCR.list_people(actor=principal, search=text, current_only=False)
    if not rows:
        print("  Nobody matches.")
        return None
    if len(rows) == 1:
        return rows[0]
    for p in rows:
        print(f"    #{p.person_id:<4} {p.full_name} ({p.category})")
    pid = _int("  Which id: ")
    return SCR.get_person(pid) if pid else None


def _check() -> SCR.Check | None:
    cid = _int("  Check id: ")
    return SCR.get_check(cid) if cid else None


def _ask(label: str, cur: Any = None) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _check_details(cur: SCR.Check | None, check_type: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    dbs = check_type == SCR.DBS
    st = _pick("Status", SCR.DBS_STATUSES if dbs else SCR.STATUSES, cur.status if cur else None)
    if st:
        out["status"] = st
    keys = [("checked_on", "Checked on"), ("checked_by", "Checked by"),
            ("reference", "Document / reference"), ("issued_on", "Issued on"),
            ("expires_on", "Expires on")]
    if dbs:
        lv = _pick("Level", SCR.LEVELS, cur.dbs_level if cur else SCR.DEFAULT_LEVEL)
        if lv:
            out["dbs_level"] = lv
        ct = _pick("Certificate", SCR.CERTIFICATE_TYPES,
                   cur.certificate_type if cur else SCR.DEFAULT_CERTIFICATE_TYPE)
        if ct:
            out["certificate_type"] = ct
        keys += [("dbs_number", "DBS certificate no."), ("applied_on", "Applied on"),
                 ("certificate_seen_on", "Certificate seen on"),
                 ("update_service_id", "Update Service id"),
                 ("last_update_check_on", "Last update check"),
                 ("next_update_check_due", "Next update check"),
                 ("risk_assessment_completed_on", "Risk assessment on"),
                 ("risk_assessment_outcome", "Risk assessment outcome"),
                 ("signed_off_by", "Signed off by"), ("signed_off_on", "Signed off on")]
    keys.append(("notes", "Notes"))
    for key, label in keys:
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = v
    if dbs:
        for key, label in (("update_service_subscribed", "Update Service"),
                           ("portability_check", "Portability check"),
                           ("risk_assessment_required", "Risk assessment required")):
            v = _ask(f"{label} (y/n)", ("y" if getattr(cur, key) else "n") if cur else "")
            if v:
                out[key] = v.lower() in ("y", "yes")
    return out


# ── The old DBS options ──────────────────────────────────────────────

def _filter(principal: Principal) -> None:
    f: dict[str, Any] = {}
    s = _prompt("  Staff (blank = all): ")
    if s:
        f["search"] = s
    for key, label, options in (("level", "Level", SCR.LEVELS),
                                ("status", "Status", SCR.DBS_STATUSES),
                                ("certificate_type", "Cert", SCR.CERTIFICATE_TYPES)):
        v = _pick(f"{label} (blank = any)", options)
        if v:
            f[key] = v
    _dbs(principal, **f)


def _per_staff(principal: Principal) -> None:
    p = _person(principal)
    if p:
        _checks_table(SCR.checks_for_person(p.person_id, actor=principal))


def _view(_principal: Principal) -> None:
    c = _check()
    if c is None:
        return
    print(f"\n  Check #{c.check_id} - {c.person_name}: {c.check_type} ({c.state})")
    for k in SCR.CHECK_FIELDS:
        v = getattr(c, k)
        if v not in (None, "", False):
            print(f"    {k.replace('_', ' '):<30} {v}")


def _new(principal: Principal) -> None:
    p = _person(principal)
    if p:
        c = SCR.add_check(p.person_id, {"check_type": SCR.DBS, **_check_details(None, SCR.DBS)},
                          actor=principal)
        print(f"  Added DBS check #{c.check_id} ({c.status}).")


def _edit(principal: Principal) -> None:
    c = _check()
    if c:
        changes = _check_details(c, c.check_type)
        if changes:
            SCR.update_check(c.check_id, changes, actor=principal)
            print("  Saved.")
        else:
            print("  Nothing changed.")


def _issue(principal: Principal) -> None:
    c = _check()
    if c:
        SCR.issue_certificate(c.check_id, dbs_number=_prompt("  DBS number: "), actor=principal,
                              issued_on=_prompt("  Issued on (blank = today): ") or None,
                              expires_on=_prompt("  Expires on (blank ok): ") or None)
        print("  Cleared.")


def _seen(principal: Principal) -> None:
    c = _check()
    if c:
        SCR.see_certificate(c.check_id, actor=principal,
                            seen_on=_prompt("  Seen on (blank = today): ") or None)
        print("  Saved.")


def _subscribe(principal: Principal) -> None:
    c = _check()
    if c:
        c = SCR.subscribe_update_service(
            c.check_id, actor=principal, update_id=_prompt("  Update Service id: ") or None,
            next_check_due=_prompt("  Next check due (blank = 12 months): ") or None)
        print(f"  Subscribed; next check due {c.next_update_check_due}.")


def _update_check(principal: Principal) -> None:
    c = _check()
    if c:
        c = SCR.record_update_check(
            c.check_id, actor=principal,
            checked_on=_prompt("  Checked on (blank = today): ") or None,
            next_check_due=_prompt("  Next check due (blank = 12 months): ") or None)
        print(f"  Saved; next check due {c.next_update_check_due}.")


def _risk(principal: Principal) -> None:
    c = _check()
    if c:
        SCR.complete_risk_assessment(c.check_id, outcome=_prompt("  Outcome: "), actor=principal,
                                     completed_on=_prompt("  Completed on: ") or None)
        print("  Saved.")


def _sign(principal: Principal) -> None:
    c = _check()
    if c:
        SCR.sign_off(c.check_id, signed_off_by=_prompt("  Signed off by: "), actor=principal,
                     signed_off_on=_prompt("  Signed off on (blank = today): ") or None)
        print("  Signed off.")


def _lapsed(principal: Principal) -> None:
    c = _check()
    if c and _yes(f"  Mark check #{c.check_id} lapsed?"):
        SCR.mark_lapsed(c.check_id, actor=principal)
        print("  Lapsed.")


def _renew(principal: Principal) -> None:
    c = _check()
    if c:
        SCR.start_renewal(c.check_id, actor=principal)
        print("  Renewing.")


def _status(principal: Principal) -> None:
    c = _check()
    if c:
        st = _pick("Status", SCR.DBS_STATUSES if c.check_type == SCR.DBS else SCR.STATUSES,
                   c.status)
        SCR.set_status(c.check_id, st or c.status, actor=principal)
        print("  Saved.")


def _delete(principal: Principal) -> None:
    c = _check()
    if c and _yes(f"  Delete check #{c.check_id} ({c.check_type}, {c.person_name})?"):
        SCR.delete_check(c.check_id, actor=principal)
        print("  Deleted.")


def _summary(principal: Principal) -> None:
    s = SCR.summary(actor=principal)
    print("\n═══ Single Central Record ═══")
    print(f"  People: {s['people']}   All checks complete: {s['complete']}")
    print("  " + ", ".join(f"{k} {n}" for k, n in sorted(s["states"].items())))
    print("\n═══ DBS Checks Summary ═══")
    for label, key in (("Total", "dbs_total"), ("Active", "dbs_active"),
                       ("Pending", "dbs_pending"), ("Renewing", "dbs_renewing"),
                       ("Expired", "dbs_expired"), ("Expiring soon", "dbs_expiring_soon"),
                       ("Update check overdue", "update_check_overdue"),
                       ("Update Service", "update_service_subscribed"),
                       ("Risk assessment pending", "risk_assessment_pending"),
                       ("Unsigned", "unsigned")):
        print(f"  {label:<24}: {s[key]}")
    for head, key in (("By level", "by_level"), ("By status", "by_status"),
                      ("By certificate type", "by_certificate_type")):
        print(f"\n  {head}:")
        for k, n in s[key].items():
            print(f"    {k or '-':<34}: {n}")


# ── New ──────────────────────────────────────────────────────────────

def _record(principal: Principal) -> None:
    cat = _pick("Category (blank = all)", SCR.CATEGORIES)
    only = _yes("  Outstanding only?")
    rows = SCR.record(actor=principal, category=cat or None, problems_only=only)
    if not rows:
        print("  (nobody)")
    for p, st in rows:
        bad = [f"{t} {_MARK[v['state']]}" for t, v in st.items() if v["state"] != "ok"]
        print(f"  #{p.person_id:<4} {p.full_name[:24]:<24} {p.category:<10} "
              + ("all checks ok" if not bad else "; ".join(bad)))


def _todo(principal: Principal) -> None:
    rows = SCR.problems(actor=principal)
    if not rows:
        print("  Nothing outstanding.")
    for x in rows:
        print(f"  {x['person'].full_name[:24]:<24} {x['check']:<32} {_MARK[x['state']]:<9} "
              f"{x['detail']}")


def _reminders(principal: Principal) -> None:
    days = _int("  Due within how many days [60]: ") or 60
    rows = SCR.reminders(actor=principal, within_days=days)
    if not rows:
        print("  Nothing due.")
    for x in rows:
        print(f"  {x['due']}  {x['person'].full_name[:24]:<24} {x['what']}")


def _person_details(cur: SCR.Person | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cat = _pick("Category", SCR.CATEGORIES, cur.category if cur else "Staff")
    if cat:
        out["category"] = cat
    for key, label in (("full_name", "Name (blank = from login / roster)"),
                       ("username", "Staff login"), ("role_title", "Post / role"),
                       ("agency_name", "Agency"), ("supply_id", "Supply roster id"),
                       ("start_date", "Start date"), ("end_date", "Leaving date"),
                       ("notes", "Notes")):
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = v
    for key, label in (("teaching_role", "Teaching post"),
                       ("leadership_role", "Management post (section 128)"),
                       ("regulated_activity", "Regulated activity"),
                       ("lived_overseas", "Lived / worked overseas"),
                       ("childcare_relevant", "Childcare disqualification relevant")):
        v = _ask(f"{label} (y/n)", ("y" if getattr(cur, key) else "n") if cur else "")
        if v:
            out[key] = v.lower() in ("y", "yes")
    return out


def _add_person(principal: Principal) -> None:
    p = SCR.create_person(_person_details(None), actor=principal)
    print(f"  Added #{p.person_id} {p.full_name}. Checks needed: "
          + ", ".join(SCR.required_checks(p)))


def _edit_person(principal: Principal) -> None:
    p = _person(principal)
    if p:
        SCR.update_person(p.person_id, _person_details(p), actor=principal)
        print("  Saved.")


def _person_checks(principal: Principal) -> None:
    p = _person(principal)
    if p is None:
        return
    print(f"\n  {p.full_name} ({p.category})")
    for t, v in SCR.person_status(p).items():
        c = v["check"]
        print(f"    {t:<32} {_MARK[v['state']]:<9} "
              + (f"#{c.check_id} {c.status} {c.checked_on or ''} by {c.checked_by or '-'}"
                 if c else ""))


def _add_any(principal: Principal) -> None:
    p = _person(principal)
    if p is None:
        return
    print("  Needed: " + ", ".join(SCR.required_checks(p)))
    t = _pick("Check", SCR.CHECK_TYPES)
    if t:
        c = SCR.add_check(p.person_id, {"check_type": t, **_check_details(None, t)},
                          actor=principal)
        print(f"  Added check #{c.check_id} ({c.state}).")


def _leaving(principal: Principal) -> None:
    p = _person(principal)
    if p:
        SCR.record_leaving(p.person_id, actor=principal,
                           end_date=_prompt("  Leaving date (blank = today): ") or None)
        print("  Saved (record kept).")


def _delete_person(principal: Principal) -> None:
    p = _person(principal)
    if p and _yes(f"  Delete {p.full_name} (added in error)?"):
        SCR.delete_person(p.person_id, actor=principal)
        print("  Deleted.")


def _add_logins(principal: Principal) -> None:
    print(f"  Added {SCR.add_from_logins(actor=principal)} member(s) of staff.")


def _sync(principal: Principal) -> None:
    print(f"  Added {SCR.sync_supply(actor=principal)} supply person(s).")


def _print(principal: Principal) -> None:
    text = SCR.scr_text(actor=principal)
    print("\n" + text)
    path = _prompt("  Save as text file (blank = no): ")
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("  Saved.")


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. single_central_record.csv): ")
    if path:
        print(f"  Exported {SCR.export_csv(path, actor=principal)} person(s).")


def _history(principal: Principal) -> None:
    p = _person(principal)
    if p:
        for h in SCR.history(p.person_id):
            print(f"  {h['at']}  {h['actor']:<12} {h['action']:<14} "
                  + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _missing(principal: Principal) -> None:
    m = SCR.missing_people(actor=principal)
    print("  Staff logins not on the record: "
          + (", ".join(t["display_name"] for t in m["logins"]) or "none"))
    print("  Supply staff not on the record: "
          + (", ".join(s.full_name for s in m["supply"]) or "none"))


_OPTIONS = {
    "1": lambda p: _dbs(p), "2": lambda p: _dbs(p, active_only=True),
    "3": lambda p: _dbs(p, expired=True), "4": lambda p: _dbs(p, expiring_soon=True),
    "5": lambda p: _dbs(p, update_check_overdue=True), "6": lambda p: _dbs(p, unsigned=True),
    "7": lambda p: _dbs(p, risk_assessment_pending=True), "8": _filter, "9": _per_staff,
    "10": _view, "12": _new, "13": _edit, "14": _issue, "15": _seen, "16": _subscribe,
    "17": _update_check, "18": _risk, "19": _sign, "20": _lapsed, "21": _renew,
    "22": _status, "23": _delete, "25": _summary, "26": _record, "27": _todo,
    "28": _reminders, "29": _add_person, "30": _edit_person, "31": _person_checks,
    "32": _add_any, "33": _leaving, "34": _delete_person, "35": _add_logins, "36": _sync,
    "37": _print, "38": _export, "39": _history, "40": _missing}

_MENU = """
   1) List all
   2) Active only
   3) Expired
   4) Expiring soon
   5) Update overdue
   6) Unsigned
   7) Risk assess. pending
   8) Filter
   9) Per-staff
  10) View
      ──────────────────
  12) New check
  13) Edit check
  14) Issue certificate
  15) Mark certificate seen
  16) Subscribe to Update Service
  17) Record update check
  18) Complete risk assessment
  19) Sign off
  20) Mark Lapsed
  21) Start renewal
  22) Change status
  23) Delete
      ──────────────────
  25) Summary
  More
  26) The record                27) To do
  28) Reminders                 29) Add person
  30) Edit person               31) Person's checks
  32) Add any check             33) Record leaving
  34) Delete person             35) Add staff logins
  36) Sync supply roster        37) Print the record
  38) Export CSV                39) History
  40) People not on the record
   0) Back"""


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("scr.view", principal=principal)
        print("\n── Single Central Record ──" + _MENU)
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
