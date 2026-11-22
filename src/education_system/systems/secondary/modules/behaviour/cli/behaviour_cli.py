"""Behaviour & Rewards in the terminal.

The old "Behaviour Log" menu keeps its options in place: 1 Log incident,
2 List incidents, 3 View incident, 4 Edit incident, 5 Set status, 6 Pupil
summary, 7 Cohort summary, 8 Pupils on -threshold, 9 Delete incident.
New: 10 Log for several pupils, 11 Note home, 12 Rewards, 13 Mark reward
presented, 14 Leaderboard, 15 House table, 16 Add / edit house, 17 Put
pupils in a house, 18 Concerns, 19 Reports, 20 Behaviour types, 21
History, 22 Export CSV. Rules live in :mod:`modules.behaviour.domain.behaviour`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (BH.ValidationError, BH.PermissionDenied, BH.NotFound)


_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _table(rows: list[BH.Entry]) -> None:
    if not rows:
        print("  (no entries)")
        return
    print(f"  {'ID':<5} {'Date':<11} {'Time':<6} {'Pupil':<26} {'Yr':<3} {'Type':<17} "
          f"{'Pol':<4} {'Pts':>4} {'Severity':<9} {'Status':<10} Description")
    for r in rows:
        print(f"  {r.entry_id:<5} {r.entry_date:<11} {r.entry_time or '':<6} "
              f"{r.pupil_name[:26]:<26} {r.pupil_year:<3} {r.incident_type[:17]:<17} "
              f"{'+' if r.polarity == 'positive' else '-':<4} {r.points:>+4d} "
              f"{r.severity:<9} {r.status:<10} {r.description[:40]}")


def _details(current: BH.Entry | None = None) -> dict[str, Any]:
    """Ask for an entry's fields; Enter keeps the current value (or the default)."""
    def ask(label: str, cur: Any) -> str:
        return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")

    out: dict[str, Any] = {}
    types = [t.name for t in BH.list_types()]
    for key, label, cur in (("entry_date", "Date YYYY-MM-DD",
                             current.entry_date if current else BH._today().isoformat()),
                            ("entry_time", "Time HH:MM", current.entry_time if current else ""),
                            ("location", "Location", current.location if current else ""),
                            ("subject", "Subject code", current.subject_code if current
                             else "")):
        v = ask(label, cur)
        if v:
            out[key] = v
    t = _pick("Type", types, current.incident_type if current else None)
    if t:
        out["incident_type"] = t
    v = ask("Points (Enter = type default)", current.points if current else "")
    if v:
        out["points"] = v
    s = _pick("Severity", BH.SEVERITIES, current.severity if current else BH.DEFAULT_SEVERITY)
    if s:
        out["severity"] = s
    for key, label, cur in (("description", "Description",
                             current.description if current else ""),
                            ("raised_by", "Raised by", current.raised_by if current else ""),
                            ("action_taken", "Action taken",
                             current.action_taken if current else ""),
                            ("notes", "Notes", current.notes if current else "")):
        v = ask(label, cur)
        if v:
            out[key] = v
    if current is None:
        share = _prompt("  Share with parents? (y/n, Enter = yes if positive): ").lower()
        if share in ("y", "n"):
            out["share_with_parents"] = share == "y"
    return out


def _entry() -> BH.Entry | None:
    eid = _int("  Entry ID: ")
    return BH.get(eid) if eid else None


def _pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil ID / admission no.: ")
    p = BH._pupil(ref) if ref else None
    if ref and p is None:
        print("  No such pupil.")
    return p


# ── Old options ──────────────────────────────────────────────────────

def _log(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    e = BH.log_incident({"pupil_id": p.pupil_id, **_details()}, actor=principal)
    print(f"\n  Logged #{e.entry_id}: {e.incident_type} {e.points:+d} for {e.pupil_name}.")
    _new_rewards([e])


def _new_rewards(entries: list[BH.Entry]) -> None:
    today = BH._today().isoformat()
    for e in entries:
        for m in BH.milestones(pupil_id=e.pupil_id, academic_year=e.academic_year,
                               unpresented=True):
            if m["reached_at"][:10] == today:
                print(f"  ★ {m['pupil_name']} has reached {m['level']} ({m['points']} points)")


def _list(_principal: Principal) -> None:
    y = _prompt("  Year (Enter = all): ")
    ref = _prompt("  Pupil ID / admission no. (Enter = all): ")
    p = BH._pupil(ref) if ref else None
    if ref and p is None:
        print("  No such pupil.")
        return
    pol = _pick("Polarity (Enter = all)", BH.POLARITIES)
    sev = _pick("Severity (Enter = all)", BH.SEVERITIES)
    st = _pick("Status (Enter = all)", BH.INCIDENT_STATUSES)
    _table(BH.list_entries(year_group=y or None, pupil_id=p.pupil_id if p else None,
                           polarity=pol, severity=sev, status=st, limit=200))


def _view(_principal: Principal) -> None:
    e = _entry()
    if e is None:
        return
    print(f"\n  #{e.entry_id}  {e.pupil_name} ({e.admission_no}) Year {e.pupil_year} "
          f"{e.form_group or ''}")
    for label, value in (("Date", f"{e.entry_date} {e.entry_time or ''}"),
                         ("Location", e.location), ("Subject", e.subject_code),
                         ("Type", f"{e.incident_type} ({e.polarity})"),
                         ("Points", f"{e.points:+d}"), ("Severity", e.severity),
                         ("Status", e.status), ("Escalated to", e.escalated_to),
                         ("Raised by", e.raised_by), ("Description", e.description),
                         ("Action taken", e.action_taken), ("Notes", e.notes),
                         ("Shared with parents", "yes" if e.share_with_parents else "no"),
                         ("Parents notified", e.parents_notified_at)):
        if value:
            print(f"  {label:<20} {value}")


def _edit(principal: Principal) -> None:
    e = _entry()
    if e is None:
        return
    if not BH.can_edit(principal, e):
        print("  Only the person who logged it (while it's open) or the behaviour lead can "
              "change it. Use 5) Set status.")
        return
    changes = _details(e)
    if changes:
        BH.update(e.entry_id, changes, actor=principal)
        print("  Saved.")


def _status(principal: Principal) -> None:
    e = _entry()
    if e is None:
        return
    st = _pick("Status", BH.INCIDENT_STATUSES, e.status)
    to = _prompt("  Escalated to (if escalating): ") if st == "Escalated" else None
    action = _prompt("  Add to action taken (optional): ")
    BH.set_status(e.entry_id, st or "", actor=principal, escalated_to=to,
                  action_taken=action or None)
    print(f"  Status now {st}.")


def _pupil_summary(_principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    s = BH.pupil_summary(p.pupil_id, academic_year=BH.current_year())
    nxt = BH.next_level(p.pupil_id)
    print(f"\n  {p.display_name} ({p.admission_no}) - {BH.current_year()}")
    print(f"  Entries {s['total']} (positive {s['positive']}, negative {s['negative']})")
    print(f"  Points {s['total_points']:+d} (positive {s['positive_points']}, "
          f"negative {s['negative_points']})")
    print(f"  House {s['house'].name if s['house'] else '-'}; rewards: "
          + (", ".join(m["level"] for m in reversed(s["milestones"])) or "none yet")
          + (f"; {nxt['needed']} to {nxt['next']}" if nxt["next"] else ""))
    for k, v in s["by_type"].items():
        print(f"    {k:<20} {v}")
    _table(s["incidents"][:30])


def _cohort(_principal: Principal) -> None:
    y = _prompt("  Year (Enter = whole school): ")
    s = BH.cohort_summary(year_group=y or None, academic_year=BH.current_year())
    print(f"\n  Entries {s['total']} ({s['pupils']} pupils) · positive {s['positive']} · "
          f"negative {s['negative']} · ratio {s['ratio']}:1 · open {s['open']}")
    for title, d in (("By type", s["by_type"]), ("By severity", s["by_severity"]),
                     ("By status", s["by_status"])):
        print(f"  {title}:")
        for k, v in d.items():
            print(f"    {k:<20} {v}")


def _threshold(_principal: Principal) -> None:
    v = _prompt(f"  Net points at or below [{BH.THRESHOLD}]: ")
    try:
        limit = int(v) if v else BH.THRESHOLD
    except ValueError:
        print("  Enter a whole number.")
        return
    y = _prompt("  Year (Enter = all): ")
    rows = BH.pupils_above_threshold(points_below=limit, year_group=y or None)
    if not rows:
        print("  (nobody)")
    for t in rows:
        print(f"  {t['pupil_name'][:30]:<30} ({t['admission_no']})  Yr {t['year_group']}  "
              f"{t['net']:+d}")


def _delete(principal: Principal) -> None:
    e = _entry()
    if e is None:
        return
    if _yes(f"  Delete #{e.entry_id} for {e.pupil_name}? (others can withdraw instead) "):
        BH.delete(e.entry_id, actor=principal, reason=_prompt("  Reason: ") or None)
        print("  Deleted.")


# ── New options ──────────────────────────────────────────────────────

def _log_many(principal: Principal) -> None:
    form = _prompt("  Form group (Enter to type pupils instead): ")
    if form:
        pupils = [p.pupil_id for p in P.list_pupils(form_group=form)]
        if not pupils:
            print("  No pupils on roll in that form.")
            return
        print(f"  {len(pupils)} pupil(s) in {form}.")
    else:
        refs = _prompt("  Pupil IDs / admission nos (comma separated): ")
        pupils = [r.strip() for r in refs.split(",") if r.strip()]
    done = BH.log_many(pupils, _details(), actor=principal)
    print(f"\n  Logged {len(done)} entr{'y' if len(done) == 1 else 'ies'}.")
    _new_rewards(done)


def _note_home(principal: Principal) -> None:
    ids = [int(x) for x in _prompt("  Entry IDs (comma separated): ").replace(" ", "")
           .split(",") if x.isdigit()]
    if not ids:
        return
    note = _prompt("  Extra message (optional): ")
    res = BH.notify_parents(ids, actor=principal, note=note or None)
    print(f"  {res['emails']} e-mail(s) prepared.")
    for p in res["no_email"]:
        print(f"  No parent e-mail for {p.display_name}")
    if res["message_id"]:
        from education_system.systems.secondary.modules.communication.domain import (
            email_outbox as E,
        )
        try:
            E.deliver(res["message_id"], principal=principal)
            print("  Sent.")
        except Exception as e:  # noqa: BLE001 - queued; shown to the user
            print(f"  Queued - delivery failed: {e}")


def _rewards(_principal: Principal) -> None:
    only_open = _yes("  Only rewards not yet presented? ")
    rows = BH.milestones(academic_year=BH.current_year(), unpresented=only_open)
    if not rows:
        print("  (none)")
    for m in rows:
        print(f"  {m['milestone_id']:<5} {m['pupil_name'][:28]:<28} Yr {m['year_group']:<3} "
              f"{m['level']:<9} {m['reached_at'][:10]}  "
              + (f"presented {m['presented_at'][:10]}" if m["presented_at"] else ""))


def _present(principal: Principal) -> None:
    ids = [int(x) for x in _prompt("  Reward IDs (comma separated): ").replace(" ", "")
           .split(",") if x.isdigit()]
    if ids:
        undo = _yes("  Undo presented instead? ")
        print(f"  {BH.present(ids, actor=principal, undo=undo)} updated.")


def _leaderboard(_principal: Principal) -> None:
    y = _prompt("  Year (Enter = all): ")
    for i, t in enumerate(BH.leaderboard(year_group=y or None), start=1):
        print(f"  {i:>3}. {t['pupil_name'][:30]:<30} Yr {t['year_group']:<3} {t['positive']}")


def _houses(_principal: Principal) -> None:
    table = BH.house_table()
    if not table:
        print("  No houses yet.")
        return
    for h in table:
        print(f"  {h['house']:<20} {h['pupils']:>4} pupils  {h['points']:>6} points  "
              f"({h['per_pupil']} each)")
    print(f"  {len(BH.without_house())} pupil(s) on roll without a house.")


def _save_house(principal: Principal) -> None:
    for h in BH.list_houses(include_retired=True):
        print(f"  {h.name} {h.colour or ''}{'' if h.active else ' (retired)'}")
    name = _prompt("  House name: ")
    if not name:
        return
    colour = _prompt("  Colour #RRGGBB (optional): ")
    retire = _yes("  Retire this house? ")
    BH.save_house(name, actor=principal, colour=colour or None, active=not retire)
    print("  Saved.")


def _assign(principal: Principal) -> None:
    houses = [h.name for h in BH.list_houses()]
    if not houses:
        print("  Add a house first (16).")
        return
    house = _pick("House (Enter = take out of house)", houses)
    form = _prompt("  Form group (Enter to type pupils instead): ")
    if form:
        ids = [p.pupil_id for p in P.list_pupils(form_group=form)]
    else:
        refs = [r.strip() for r in _prompt("  Pupil IDs / admission nos: ").split(",")
                if r.strip()]
        ids = [p.pupil_id for p in (BH._pupil(r) for r in refs) if p]
    if not ids:
        print("  No pupils found.")
        return
    print(f"  {BH.assign_house(ids, house, actor=principal)} pupil(s) updated.")


def _concerns(_principal: Principal) -> None:
    y = _prompt("  Year (Enter = all): ")
    rows = BH.concerns(year_group=y or None)
    if not rows:
        print("  No concerns.")
    for c in rows:
        print(f"  {'!' if c['severity'] > 1 else ' '} {c['pupil_name'][:28]:<28} "
              f"({c['admission_no']}) Yr {c['year_group']}: {'; '.join(c['reasons'])}")


def _reports(_principal: Principal) -> None:
    by = _pick("Group by", ("type", "subject", "staff", "weekday", "hour", "year"), "type")
    y = _prompt("  Year (Enter = all): ")
    rows = BH.analysis(by=by or "type", year_group=y or None,
                       academic_year=BH.current_year())
    print(f"\n  {'Group':<26} {'Pos':>5} {'Neg':>5} {'Net':>6} {'Pupils':>7}")
    for g in rows:
        print(f"  {g['group'][:26]:<26} {g['positive']:>5} {g['negative']:>5} "
              f"{g['points']:>+6d} {g['pupils']:>7}")


def _types(principal: Principal) -> None:
    for t in BH.list_types(include_retired=True):
        print(f"  {t.name:<20} {t.polarity:<9} {t.default_points:+d}"
              f"{'' if t.active else '  (retired)'}")
    if not BH.is_editor(principal) or not _yes("  Add or change a type? "):
        return
    name = _prompt("  Type name: ")
    cur = BH.get_type(name)
    pol = _pick("Polarity", BH.POLARITIES, cur.polarity if cur else None)
    pts = _prompt("  Default points" + (f" [{cur.default_points}]" if cur else "") + ": ")
    retire = _yes("  Retire it? ")
    BH.save_type(name, pol or "", pts or (cur.default_points if cur else None),
                 actor=principal, active=not retire)
    print("  Saved.")


def _history(_principal: Principal) -> None:
    e = _entry()
    if e is None:
        return
    rows = BH.history(e.entry_id)
    if not rows:
        print("  No changes recorded.")
    for h in rows:
        print(f"  {h['at']}  {h['actor']:<14} {h['action']:<10} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to [behaviour.csv]: ") or "behaviour.csv"
    y = _prompt("  Year (Enter = all): ")
    print(f"  Exported {BH.export_csv(path, actor=principal, year_group=y or None)} "
          f"entries to {path}.")


_OPTIONS = {"1": _log, "2": _list, "3": _view, "4": _edit, "5": _status,
            "6": _pupil_summary, "7": _cohort, "8": _threshold, "9": _delete,
            "10": _log_many, "11": _note_home, "12": _rewards, "13": _present,
            "14": _leaderboard, "15": _houses, "16": _save_house, "17": _assign,
            "18": _concerns, "19": _reports, "20": _types, "21": _history, "22": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("behaviour.view")
        print("\n  ── Behaviour Log ──")
        print("    1) Log incident\n    2) List incidents\n    3) View incident"
              "\n    4) Edit incident\n    5) Set status\n    6) Pupil summary"
              "\n    7) Cohort summary\n    8) Pupils on -threshold\n    9) Delete incident")
        print("  More")
        print("   10) Log for several pupils\n   11) Note home\n   12) Rewards"
              "\n   13) Mark reward presented\n   14) Leaderboard\n   15) House table"
              "\n   16) Add / edit house\n   17) Put pupils in a house\n   18) Concerns"
              "\n   19) Reports\n   20) Behaviour types\n   21) History\n   22) Export CSV")
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
