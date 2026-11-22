"""Pupil premium in the terminal.

The old Pupil Premium menu keeps its options in place: 1 Set / update
eligibility, 2 List records, 3 View record + interventions, 4 Delete record,
5 Add intervention, 6 Edit intervention, 7 Delete intervention, 8 Cohort
summary. New, under "More": 9 Cohort (with FSM from pupil records and Ever 6),
10 Record FSM from pupil records, 11 Funding rates, 12 Strategy statement,
13 Spending plan, 14 Add plan line, 15 Edit plan line, 16 Allocate a line to
pupils, 17 Impact (gaps), 18 Line impact, 19 Copy plan to next year, 20
History, 21 Export CSV. Rules live in :mod:`modules.finance.domain.pupil_premium`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.finance.domain import pupil_premium as PP
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (PP.ValidationError, PP.PermissionDenied, PP.NotFound)
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


def _year() -> str:
    return _prompt(f"  School year [{PP.current_year()}]: ") or PP.current_year()


def _money(v: float | None) -> str:
    return "-" if v is None else f"£{v:,.2f}"


_EL = [("category", "Category", PP.CATEGORIES), ("status", "Status", PP.PP_STATUSES),
       ("funding_amount", "Funding £ (blank = the rate)", None),
       ("start_date", "Start date", None), ("end_date", "End date", None),
       ("eligibility_source", "Eligibility source", None), ("keyworker", "Keyworker", None),
       ("notes", "Notes", None)]
_ACT = [("title", "Title", None), ("description", "Description", None),
        ("spend", "Spend £", None), ("start_date", "Start date", None),
        ("end_date", "End date", None), ("status", "Status", PP.INTERVENTION_STATUSES),
        ("impact_rating", "Impact", PP.IMPACT_RATINGS), ("impact_notes", "Impact notes", None),
        ("line_id", "Plan line ID (blank ok)", None), ("notes", "Notes", None)]
_LINE = [("tier", "Tier", PP.TIERS), ("title", "Title", None),
         ("description", "Description", None), ("evidence", "Evidence (e.g. EEF)", None),
         ("challenge", "Challenge it addresses", None),
         ("success_criteria", "Success criteria", None), ("owner", "Owner", None),
         ("planned_cost", "Planned cost £", None), ("actual_cost", "Actual cost £", None),
         ("status", "Status", PP.INTERVENTION_STATUSES),
         ("impact_rating", "Impact", PP.IMPACT_RATINGS), ("impact_notes", "Impact notes", None)]


def _table(rows: list[PP.Eligibility]) -> None:
    if not rows:
        print("  (no records)")
        return
    print(f"  {'ID':<4} {'AYear':<8} {'Pupil':<24} {'Yr':<3} {'Category':<26} {'Status':<11} "
          f"{'Funding':>10}  Keyworker")
    for e in rows:
        print(f"  {e.eligibility_id:<4} {e.academic_year:<8} {e.pupil_name[:24]:<24} "
              f"{e.pupil_year:<3} {e.category[:26]:<26} {e.status:<11} "
              f"{_money(e.funding_amount):>10}  {e.keyworker or ''}")


def _acts(rows: list[PP.Activity]) -> None:
    if not rows:
        print("  (no interventions)")
    for a in rows:
        print(f"    #{a.activity_id:<4} {a.start_date} {a.status:<9} {_money(a.spend):>9} "
              f"{a.impact_rating:<17} {a.title}")


# ── The old menu ─────────────────────────────────────────────────────

def _upsert(principal: Principal) -> None:
    e = PP.upsert({"pupil_id": _prompt("  Pupil ID / admission no.: "),
                   "academic_year": _year(), **_ask(_EL)}, actor=principal)
    print(f"  Saved #{e.eligibility_id}: {e.pupil_name} ({e.academic_year}) - {e.category}")


def _list(_principal: Principal) -> None:
    _table(PP.list_records(year_group=_prompt("  Year group (blank = all): ") or None,
                           academic_year=_year(),
                           category=_pick("Category (blank = all)", PP.CATEGORIES) or None,
                           status=_pick("Status (blank = all)", PP.PP_STATUSES) or None))


def _record() -> PP.Eligibility | None:
    eid = _int("  Record ID: ")
    return PP.get(eid) if eid else None


def _view(_principal: Principal) -> None:
    e = _record()
    if e is None:
        return
    s = PP.record_summary(e.eligibility_id)
    print(f"\n  #{e.eligibility_id} {e.pupil_name} ({e.admission_no}) {e.academic_year}")
    for key, label, _c in _EL:
        v = getattr(e, key)
        if v not in (None, ""):
            print(f"    {label.split(' (')[0] + ':':<20} {v}")
    print(f"  Funding {_money(s['funding'])}   spent {_money(s['total_spend'])}   remaining "
          f"{_money(s['remaining'])}")
    _acts(s["interventions"])


def _delete(principal: Principal) -> None:
    e = _record()
    if e and _yes(f"  Delete record #{e.eligibility_id}?"):
        PP.delete(e.eligibility_id, actor=principal)
        print("  Deleted.")


def _add_act(principal: Principal) -> None:
    ref = _prompt("  Record ID, or pupil ID / admission no.: ")
    key = "pp_id" if ref.isdigit() and _yes("  Is that a record ID?") else "pupil_id"
    a = PP.add_intervention({key: ref, **_ask(_ACT)}, actor=principal)
    print(f"  Added intervention #{a.activity_id}.")


def _edit_act(principal: Principal) -> None:
    aid = _int("  Intervention ID: ")
    if aid:
        PP.update_intervention(aid, _ask(_ACT, PP.get_activity(aid)), actor=principal)
        print("  Saved.")


def _del_act(principal: Principal) -> None:
    aid = _int("  Intervention ID: ")
    if aid and _yes(f"  Delete intervention #{aid}?"):
        PP.delete_intervention(aid, actor=principal)
        print("  Deleted.")


def _summary(_principal: Principal) -> None:
    s = PP.cohort_summary(year_group=_prompt("  Year group (blank = all): ") or None,
                          academic_year=_year())
    print(f"\n  Pupils: {s['total']} of {s['on_roll']}   Funding: {_money(s['total_funding'])}   "
          f"Interventions: {s['interventions']}   Spend: {_money(s['total_spend'])}   "
          f"Remaining: {_money(s['remaining'])}   Without an activity: "
          f"{s['pp_without_activities']}")
    for key in ("by_category", "by_status"):
        print(f"  {key[3:].title()}: " + ", ".join(f"{k} {v}" for k, v in s[key].items()))


# ── New ──────────────────────────────────────────────────────────────

def _cohort(_principal: Principal) -> None:
    rows = PP.cohort(academic_year=_year(),
                     year_group=_prompt("  Year group (blank = all): ") or None)
    for r in rows:
        p = r["pupil"]
        print(f"  {p.admission_no:<10} {p.display_name[:24]:<24} Yr{p.year_group:<3} "
              f"{', '.join(r['categories'])[:40]:<40} {_money(r['funding']):>10} "
              f"{'(provisional: ' + ', '.join(r['provisional']) + ')' if r['provisional'] else ''}")
    print(f"  {len(rows)} pupil(s), {_money(sum(r['funding'] for r in rows))}")


def _snapshot(principal: Principal) -> None:
    print(f"  Added {PP.record_fsm_from_pupils(actor=principal, academic_year=_year())} FSM "
          "record(s) from pupil records.")


def _rates(principal: Principal) -> None:
    year = _year()
    for k, v in PP.rates(year).items():
        print(f"  {k:<28} {_money(v)}")
    if PP.is_editor(principal) and _yes("  Change a rate?"):
        PP.set_rate(year, _pick("Category", PP.CATEGORIES) or "", _prompt("  Amount £: "),
                    actor=principal)
        print("  Saved.")


def _strategy(principal: Principal) -> None:
    year = _year()
    print("\n" + PP.strategy_text(year))
    if PP.is_editor(principal) and _yes("\n  Edit the statement?"):
        st = PP.strategy(year)

        class _S:
            pass
        cur = _S()
        for k, v in st.items():
            setattr(cur, k, v)
        PP.save_strategy(year, _ask([
            ("statement", "Statement of intent", None), ("challenges", "Challenges", None),
            ("intended_outcomes", "Intended outcomes", None), ("lead", "Lead", None),
            ("governor", "Governor", None), ("budget_override", "Budget override £", None),
            ("carried_forward", "Carried forward £", None),
            ("published_on", "Published on", None), ("review_date", "Review date", None),
            ("reviewed_on", "Reviewed on", None), ("notes", "Notes", None)], cur),
            actor=principal)
        print("  Saved.")


def _plan(_principal: Principal) -> None:
    year = _year()
    s = PP.plan_summary(year)
    b = s["budget"]
    print(f"\n  Budget {_money(b['total'])} (allocation {_money(b['allocation'])}, carried "
          f"forward {_money(b['carried_forward'])})   planned {_money(s['planned'])}   spent "
          f"{_money(s['actual'])}   unallocated {_money(s['unallocated'])}")
    for t in s["tiers"]:
        print(f"\n  {t['tier']}: planned {_money(t['planned'])} "
              f"({t['share'] if t['share'] is not None else '-'}%), spent {_money(t['actual'])}")
        for x in PP.list_lines(year, tier=t["tier"]):
            print(f"    #{x.line_id:<4} {x.title[:36]:<36} {_money(x.planned_cost):>10} "
                  f"{x.status:<9} {x.impact_rating}")
    for w in s["warnings"]:
        print(f"  ! {w}")


def _add_line(principal: Principal) -> None:
    x = PP.add_line(_year(), _ask(_LINE), actor=principal)
    print(f"  Added line #{x.line_id}.")


def _edit_line(principal: Principal) -> None:
    lid = _int("  Line ID: ")
    if lid:
        PP.update_line(lid, _ask(_LINE, PP.get_line(lid)), actor=principal)
        print("  Saved.")


def _allocate(principal: Principal) -> None:
    lid = _int("  Line ID: ")
    if not lid:
        return
    refs = _prompt("  Pupil IDs / admission nos. (comma-separated): ")
    ids = [p.pupil_id for p in (PP._pupil(r.strip()) for r in refs.split(",") if r.strip())
           if p]
    res = PP.allocate(lid, ids, actor=principal,
                      spend_each=_prompt("  Spend each £ (blank = share the line): ") or None)
    print(f"  Added {len(res['added'])}, already had it {res['skipped']}.")
    for a in res["not_pp"]:
        print(f"  ! {a.pupil_name} isn't pupil premium this year")


def _impact(_principal: Principal) -> None:
    r = PP.impact(academic_year=_year(),
                  year_group=_prompt("  Year group (blank = all): ") or None)
    print(f"\n  Pupil premium {r['pp']} pupils, others {r['other']}")
    print(f"  {'Measure':<32} {'PP':>8} {'Others':>8} {'Gap':>8}")
    for m in r["measures"]:
        print(f"  {m['measure']:<32} {_n(m['pp']):>8} {_n(m['other']):>8} {_n(m['gap']):>8}  "
              f"({m['better']} is better)")


def _n(v: float | None) -> str:
    return "-" if v is None else f"{v:g}"


def _line_impact(_principal: Principal) -> None:
    lid = _int("  Line ID: ")
    if lid:
        r = PP.line_impact(lid)
        print(f"\n  {r['line'].title}: {r['pupils']} pupils ({r['pp_pupils']} PP), spend "
              f"{_money(r['spend'])}")
        print(f"  Attendance {_n(r['attendance'])}% vs PP cohort {_n(r['cohort_attendance'])}%")
        print(f"  Incidents per pupil {_n(r['incidents'])} vs PP cohort "
              f"{_n(r['cohort_incidents'])}")
        print("  Impact: " + ", ".join(f"{k} {v}" for k, v in r["by_impact"].items()))


def _copy(principal: Principal) -> None:
    year = _year()
    print(f"  Copied {PP.copy_plan(year, actor=principal)} line(s) to {PP.next_year(year)}.")


def _history(_principal: Principal) -> None:
    for h in PP.history():
        print(f"  {h['at']}  {h['actor']:<12} {h['item']:<11} {h['action']:<12} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. pupil_premium.csv): ")
    if path:
        print(f"  Exported {PP.export_csv(path, actor=principal, academic_year=_year())} "
              "pupil(s).")


_OPTIONS = {"1": _upsert, "2": _list, "3": _view, "4": _delete, "5": _add_act,
            "6": _edit_act, "7": _del_act, "8": _summary, "9": _cohort, "10": _snapshot,
            "11": _rates, "12": _strategy, "13": _plan, "14": _add_line, "15": _edit_line,
            "16": _allocate, "17": _impact, "18": _line_impact, "19": _copy,
            "20": _history, "21": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("pupil_premium.view")
        print("\n  ── Pupil Premium ──")
        print("  Records\n    1) Set / update eligibility\n    2) List records"
              "\n    3) View record + interventions\n    4) Delete record")
        print("  Interventions\n    5) Add intervention\n    6) Edit intervention"
              "\n    7) Delete intervention")
        print("  Reports\n    8) Cohort summary")
        print("  More")
        print("    9) Cohort (FSM from pupil records, Ever 6)\n   10) Record FSM from pupil "
              "records\n   11) Funding rates\n   12) Strategy statement\n   13) Spending plan"
              "\n   14) Add plan line\n   15) Edit plan line\n   16) Allocate a line to pupils"
              "\n   17) Impact (gaps)\n   18) Line impact\n   19) Copy plan to next year"
              "\n   20) History\n   21) Export CSV")
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
