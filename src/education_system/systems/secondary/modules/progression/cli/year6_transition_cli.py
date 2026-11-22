"""Year 6 Transition (planning the incoming Year 7 cohort), in the terminal.

1 Cohort, 2 Sync, 3 Pupil details, 4 Transition report, 5 Edit details,
6 Feeder schools, 7 Liaison (list / record / delete), 8 Events (list / new /
edit / delete), 9 Invite / register / mark attendance, 10 Friendships and
keep-apart, 11 Form allocation (summary / auto-suggest / move / warnings /
publish / unlock), 12 Enhanced transition, 13 Start in September, 14 Exports,
15 Change intake year. Rules live in
:mod:`modules.progression.domain.year6_transition`.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.modules.progression.domain import year6_allocation as YA
from education_system.systems.secondary.modules.progression.domain import year6_events as YE
from education_system.systems.secondary.modules.progression.domain import year6_transition as Y6
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (Y6.ValidationError, Y6.PermissionDenied, Y6.NotFound, P.DuplicatePupil)
_problem = prompts.problem
_state: dict[str, Any] = {"year": ""}


def _year() -> str:
    return _state["year"] or Y6.default_intake()


def _ask_date(label: str, default: str | None = None) -> str | None:
    """A date as YYYY-MM-DD (Enter keeps *default*); re-asks until valid."""
    while True:
        v = _prompt(f"  {label} (YYYY-MM-DD){f' [{default}]' if default else ''}: ")
        if not v:
            return default
        try:
            return _dt.date.fromisoformat(v).isoformat()
        except ValueError:
            print("  Use the form 2027-07-02.")


def _choose(options: list[str], label: str, default: str | None = None) -> str | None:
    """Pick from a fixed list by number (Enter keeps *default*)."""
    for n, o in enumerate(options, 1):
        print(f"   {n:>2}) {o}")
    n = prompts.ask_int(f"  {label}{f' [{default}]' if default else ''}: ")
    return options[n - 1] if n and 1 <= n <= len(options) else default


def _list(principal: Principal, include_inactive: bool = False) -> list[Y6.CohortRow]:
    rows = Y6.cohort(_year(), actor=principal, include_inactive=include_inactive)
    if not rows:
        print("  Nobody in this intake yet (Sync reads the platform queue and admissions).")
    for n, r in enumerate(rows, 1):
        flags = " ".join(x for x in (r.sen_status if r.sen_status in ("K", "E") else "",
                                     "PP" if r.pupil_premium else "",
                                     "ENH" if r.enhanced else "",
                                     "SG" if r.safeguarding else "") if x)
        print(f"  {n:>3}) {r.name:<26} {(r.feeder_school or '')[:22]:<22} "
              f"{r.status_label:<14} KS2 {r.ks2_reading or '-'}/{r.ks2_maths or '-'} "
              f"{r.form_name or '-':<5} {r.progress_label:<5} {flags}")
    return rows


def _pick(principal: Principal, *, include_inactive: bool = False) -> Y6.CohortRow | None:
    rows = _list(principal, include_inactive)
    n = prompts.ask_int("  Child number: ") if rows else None
    return rows[n - 1] if n and 1 <= n <= len(rows) else None


def _pick_many(principal: Principal) -> list[int]:
    rows = _list(principal)
    text = _prompt("  Child numbers (e.g. 1,3,5-8): ")
    out: list[int] = []
    for part in text.replace(" ", "").split(","):
        if "-" in part:
            a, _s, b = part.partition("-")
            if a.isdigit() and b.isdigit():
                out += [rows[i - 1].cohort_id for i in range(int(a), int(b) + 1)
                        if 1 <= i <= len(rows)]
        elif part.isdigit() and 1 <= int(part) <= len(rows):
            out.append(rows[int(part) - 1].cohort_id)
    return list(dict.fromkeys(out))


# ── Cohort ───────────────────────────────────────────────────────────

def _cohort(principal: Principal) -> None:
    print("  " + ", ".join(f"{k}: {v}" for k, v in Y6.counts(_year(), actor=principal).items()))
    _list(principal, include_inactive=_yes("  Include children not coming?"))


def _sync(principal: Principal) -> None:
    out = Y6.sync(_year(), actor=principal)
    print(f"  Platform {out['platform']}, admissions {out['admissions']}, new {out['new']}, "
          f"report names {out['report_names']} (matched {out['resolved']})")


def _details(principal: Principal) -> None:
    r = _pick(principal, include_inactive=True)
    if r:
        print("\n" + Y6.pupil_text(r.cohort_id, actor=principal))


def _report(principal: Principal) -> None:
    r = _pick(principal)
    if r:
        print("\n" + Y6.report_text(Y6.transition_report(r.cohort_id, actor=principal)))


def _edit(principal: Principal) -> None:
    r = _pick(principal, include_inactive=True)
    if not r:
        return
    changes: dict = {}
    if Y6.is_editor(principal):
        v = prompts.ask("Feeder primary", r.feeder_school)
        if v is not None:
            changes["feeder_school"] = v
        g = _choose(list(P.GENDERS), "Gender", r.gender)
        if g and g != r.gender:
            changes["gender"] = g
        for key, label, cur in (("ks2_reading", "KS2 reading scaled score", r.ks2_reading),
                                ("ks2_maths", "KS2 maths scaled score", r.ks2_maths)):
            v = prompts.ask(f"{label} (80-120)", str(cur) if cur else None)
            if v is not None:
                changes[key] = v
        v = prompts.ask("Notes", r.notes)
        if v is not None:
            changes["notes"] = v
    if Y6.can_see_needs(principal):
        s = _choose(list(P.SEN_STATUSES), "SEN status", r.sen_status)
        if s and s != r.sen_status:
            changes["sen_status"] = s
        for key, label, cur in (("pupil_premium", "Pupil premium", r.pupil_premium),
                                ("fsm", "Free school meals", r.fsm),
                                ("lac", "Looked after / previously", r.lac),
                                ("eal", "EAL", r.eal)):
            v = prompts.ask(f"{label} (y/n)", "y" if cur else "n" if cur is not None else None)
            if v is not None:
                changes[key] = v
    Y6.update_row(r.cohort_id, changes, actor=principal)
    print("  Saved.")


# ── Feeders and liaison ──────────────────────────────────────────────

def _feeders(principal: Principal) -> None:
    for d in Y6.feeder_schools(_year(), actor=principal):
        extra = f" SEN {d['sen']} PP {d['pupil_premium']}" if d["sen"] is not None else ""
        print(f"  {d['school'][:34]:<34} coming {d['expected']:>3} (platform {d['platform']}, "
              f"admissions {d['admissions']}) enhanced {d['enhanced']}{extra}  contacts "
              f"{d['contacts']} last {d['last_contact'] or '-'}")


def _liaison_data(school_default: str | None, kind_default: str) -> dict:
    schools = sorted({d["school"] for d in Y6.feeder_schools(_year(), actor=_state["actor"])})
    print("  Primary school (number, or type a name):")
    for n, s in enumerate(schools, 1):
        print(f"   {n:>2}) {s}")
    v = _prompt(f"  School{f' [{school_default}]' if school_default else ''}: ")
    school = schools[int(v) - 1] if v.isdigit() and 1 <= int(v) <= len(schools) else \
        (v or school_default)
    return {"school": school,
            "kind": _choose(list(Y6.LIAISON_KINDS), "Kind", kind_default),
            "held_on": _ask_date("Date", _dt.date.today().isoformat()),
            "staff_name": _prompt("  Our member of staff: "),
            "contact_name": _prompt("  Their contact (e.g. Y6 teacher): "),
            "summary": _prompt("  What was discussed: "),
            "follow_up": _prompt("  Follow-up: ")}


def _liaison(principal: Principal) -> None:
    rows = Y6.liaison(_year(), actor=principal)
    for n, r in enumerate(rows, 1):
        print(f"  {n:>3}) {r['held_on']} {r['kind']:<24} {r['school'][:24]:<24} "
              f"{r['pupil'][:20]:<20} {(r['summary'] or '')[:50]}")
    print("  a) Record a school contact  p) Note about a child  d) Delete  Enter) Back")
    c = _prompt("  Choose: ").lower()
    if c == "a":
        Y6.add_liaison(_year(), _liaison_data(None, "Visit to primary"), actor=principal)
        print("  Recorded.")
    elif c == "p":
        r = _pick(principal)
        if r:
            Y6.add_liaison(_year(), _liaison_data(r.feeder_school, "Y6 teacher conversation"),
                           actor=principal, cohort_id=r.cohort_id)
            print("  Recorded.")
    elif c == "d" and rows:
        n = prompts.ask_int("  Number to delete: ")
        if n and 1 <= n <= len(rows) and _yes("  Delete it?"):
            Y6.delete_liaison(rows[n - 1]["liaison_id"], actor=principal)
            print("  Deleted.")


# ── Events ───────────────────────────────────────────────────────────

def _event_list(principal: Principal) -> list[dict]:
    rows = YE.events(_year(), actor=principal)
    if not rows:
        print("  No events yet.")
    for n, e in enumerate(rows, 1):
        print(f"  {n:>2}) {e['event_date']} {e.get('start_time') or '':<5} {e['title'][:30]:<30} "
              f"{e['audience']:<26} invited {e['invited']} attended {e['attended']}")
    return rows


def _pick_event(principal: Principal) -> dict | None:
    rows = _event_list(principal)
    n = prompts.ask_int("  Event number: ") if rows else None
    return rows[n - 1] if n and 1 <= n <= len(rows) else None


def _event_data(e: dict) -> dict:
    return {"event_type": _choose(list(Y6.EVENT_TYPES), "Type", e.get("event_type")),
            "title": prompts.ask("Title (blank = the type)", e.get("title")) or e.get("title"),
            "event_date": _ask_date("Date", e.get("event_date")),
            "start_time": _choose(list(Y6.TIMES), "Starts (number)", e.get("start_time")),
            "end_time": _choose(list(Y6.TIMES), "Ends (number)", e.get("end_time")),
            "audience": _choose(list(Y6.AUDIENCES), "For", e.get("audience")),
            "location": prompts.ask("Where", e.get("location")) or e.get("location"),
            "notes": prompts.ask("Notes", e.get("notes")) or e.get("notes")}


def _events(principal: Principal) -> None:
    _event_list(principal)
    print("  n) New  e) Edit  d) Delete  Enter) Back")
    c = _prompt("  Choose: ").lower()
    if c == "n":
        YE.create_event(_year(), _event_data({}), actor=principal)
        print("  Added.")
    elif c == "e":
        ev = _pick_event(principal)
        if ev:
            YE.update_event(ev["event_id"], _event_data(ev), actor=principal)
            print("  Saved.")
    elif c == "d":
        ev = _pick_event(principal)
        if ev and _yes(f"  Delete {ev['title']} and its register?"):
            YE.delete_event(ev["event_id"], actor=principal)
            print("  Deleted.")


def _register(principal: Principal) -> None:
    ev = _pick_event(principal)
    if not ev:
        return
    reg = YE.register(ev["event_id"], actor=principal)
    for n, d in enumerate(reg, 1):
        print(f"  {n:>3}) {d['row'].name:<28} {Y6.ATTENDANCE[d['attendance']]}")
    print("  i) Invite the audience  c) Invite children  m) Mark attendance  Enter) Back")
    c = _prompt("  Choose: ").lower()
    if c == "i":
        print(f"  {YE.invite(ev['event_id'], actor=principal)} invited.")
    elif c == "c":
        print(f"  {YE.invite(ev['event_id'], _pick_many(principal), actor=principal)} invited.")
    elif c == "m" and reg:
        att = _choose(list(Y6.ATTENDANCE), "Attendance")
        text = _prompt("  Register numbers (e.g. 1,2,4-9, or 'all'): ")
        idx = range(1, len(reg) + 1) if text.lower() == "all" else [
            int(x) for x in text.replace(" ", "").split(",") if x.isdigit()]
        ids = [reg[i - 1]["cohort_id"] for i in idx if 1 <= i <= len(reg)]
        if att:
            print(f"  {YE.mark(ev['event_id'], ids, att, actor=principal)} marked.")


# ── Friendships ──────────────────────────────────────────────────────

def _friends(principal: Principal) -> None:
    rows = Y6.relationships(_year(), actor=principal)
    for n, r in enumerate(rows, 1):
        print(f"  {n:>3}) {r['pupil'][:24]:<24} {r['kind_label']:<19} {r['other_label'][:30]:<30} "
              f"({r['source_label']})")
    print("  a) Add  l) Link an unmatched name  r) Remove  Enter) Back")
    c = _prompt("  Choose: ").lower()
    if c == "a":
        print("  The child:")
        me = _pick(principal)
        if not me:
            return
        kind = _choose(list(Y6.RELATION_KINDS.values()), "Request")
        print("  The other child:")
        other = _pick(principal)
        if kind and other:
            k = next(k for k, v in Y6.RELATION_KINDS.items() if v == kind)
            Y6.add_relationship(me.cohort_id, k, actor=principal,
                                other_cohort_id=other.cohort_id,
                                note=_prompt("  Note (optional): ") or None)
            print("  Added.")
    elif c in ("l", "r") and rows:
        n = prompts.ask_int("  Row number: ")
        if not (n and 1 <= n <= len(rows)):
            return
        if c == "r":
            Y6.remove_relationship(rows[n - 1]["rel_id"], actor=principal)
            print("  Removed.")
        else:
            other = _pick(principal)
            if other:
                Y6.link_relationship(rows[n - 1]["rel_id"], other.cohort_id, actor=principal)
                print("  Linked.")


# ── Form allocation ──────────────────────────────────────────────────

def _forms(principal: Principal) -> None:
    pub = Y6.publication(_year())
    if pub:
        print(f"  Published {pub['published_at'][:16]} by {pub['published_by']}")
    for f in YA.form_summary(_year(), actor=principal):
        b = f["bands"]
        sen = f" SEN {f['sen']}" if f["sen"] is not None else ""
        print(f"  {f['name']:<16} {f['size']:>3}/{f['capacity'] or '-':<3} F{f['female']} "
              f"M{f['male']} other {f['other']}  higher {b['Higher']} expected {b['Expected']} working towards "
              f"{b['Working towards']} none {b['No KS2']}{sen} feeders {f['feeders']}")
    for w in YA.warnings(_year(), actor=principal):
        print(f"  ! {w['text']}")
    print("  s) Auto-suggest  m) Move a child  p) Publish  u) Unlock  c) Clear suggestions  "
          "Enter) Back")
    c = _prompt("  Choose: ").lower()
    if c == "s":
        s = YA.suggest(_year(), actor=principal, keep_manual=not _yes(
            "  Re-place children moved by hand too?"))
        counts: dict[str, int] = {}
        for name in s.plan.values():
            counts[name] = counts.get(name, 0) + 1
        print("  " + ", ".join(f"{k}: {n}" for k, n in sorted(counts.items())))
        for note in s.notes:
            print(f"  - {note}")
        if _yes("  Save this allocation?"):
            print(f"  {YA.apply_plan(_year(), s.plan, actor=principal)} placed.")
    elif c == "m":
        r = _pick(principal)
        if r:
            names = [f["name"] for f in YA.forms()]
            form = _choose(names + ["(take out of form)"], "Form")
            if form:
                YA.move(r.cohort_id, None if form.startswith("(") else form, actor=principal)
                print("  Moved.")
    elif c == "p" and _yes("  Publish (locks the allocation, sets matched pupils' forms)?"):
        for note in YA.publish(_year(), actor=principal):
            print(f"  - {note}")
    elif c == "u":
        YA.unpublish(_year(), actor=principal, reason=_prompt("  Why: "))
        print("  Unlocked.")
    elif c == "c" and _yes("  Clear the suggested placements?"):
        print(f"  {YA.clear_allocation(_year(), actor=principal)} cleared.")


# ── Enhanced transition ──────────────────────────────────────────────

def _enhanced(principal: Principal) -> None:
    rows = Y6.enhanced(_year(), actor=principal)
    for n, d in enumerate(rows, 1):
        r = d["row"]
        print(f"  {n:>3}) {r.name:<26} {d['status']:<12} visits {d['visits_attended']}/"
              f"{d['extra_visits']} key adult {d['key_adult'] or '-'} story "
              f"{'sent' if d['social_story_sent'] else '-'}  ({'; '.join(r.enhanced_reasons)})")
    print("  e) Edit a plan  a) Add a child  r) Take off (added by hand)  Enter) Back")
    c = _prompt("  Choose: ").lower()
    if c == "e" and rows:
        n = prompts.ask_int("  Number: ")
        if n and 1 <= n <= len(rows):
            d = rows[n - 1]
            Y6.set_plan(d["row"].cohort_id, {
                "status": _choose(list(Y6.ENHANCED_STATUSES), "Status", d["status"]),
                "extra_visits": prompts.ask("Extra visits planned", str(d["extra_visits"]))
                or d["extra_visits"],
                "key_adult": prompts.ask("Key adult", d["key_adult"]) or d["key_adult"],
                "social_story_sent": _yes("  Social story sent?"),
                "plan": prompts.ask("Plan", d["plan"]) or d["plan"]}, actor=principal)
            print("  Saved.")
    elif c == "a":
        r = _pick(principal)
        if r:
            Y6.add_to_enhanced(r.cohort_id, actor=principal, reason=_prompt("  Why: "))
            print("  Added.")
    elif c == "r" and rows:
        n = prompts.ask_int("  Number: ")
        if n and 1 <= n <= len(rows):
            Y6.remove_from_enhanced(rows[n - 1]["row"].cohort_id, actor=principal)
            print("  Taken off.")


# ── September start, exports, year ───────────────────────────────────

def _start(principal: Principal) -> None:
    date = _ask_date("First day", _dt.date.today().isoformat())
    if _yes("  Start everyone not yet started? (No = one child)"):
        for name, notes in Y6.start_all(_year(), actor=principal, start_date=date).items():
            print(f"  {name}")
            for n in notes:
                print(f"    - {n}")
        return
    r = _pick(principal)
    if r:
        for n in Y6.start_pupil(r.cohort_id, actor=principal, start_date=date):
            print(f"  - {n}")


def _exports(principal: Principal) -> None:
    what = _choose(["Cohort CSV", "Event register", "Form lists"], "Export")
    stem = _year().replace("/", "-")
    if what == "Cohort CSV":
        path = _prompt(f"  Save to [year6_cohort_{stem}.csv]: ") or f"year6_cohort_{stem}.csv"
        print(f"  Exported {Y6.export_cohort_csv(_year(), path, actor=principal)}.")
    elif what == "Event register":
        ev = _pick_event(principal)
        if ev:
            path = _prompt(f"  Save to [register_{ev['event_date']}.csv]: ") or \
                f"register_{ev['event_date']}.csv"
            print(f"  Exported {YE.export_register(ev['event_id'], path, actor=principal)}.")
    elif what == "Form lists":
        path = _prompt(f"  Save to [year7_forms_{stem}.csv]: ") or f"year7_forms_{stem}.csv"
        print(f"  Exported {Y6.export_form_lists(_year(), path, actor=principal)}.")


def _change_year(_principal: Principal) -> None:
    y = _choose(Y6.intake_choices(), "Intake year", _year())
    if y:
        _state["year"] = y


_OPTIONS = {"1": _cohort, "2": _sync, "3": _details, "4": _report, "5": _edit, "6": _feeders,
            "7": _liaison, "8": _events, "9": _register, "10": _friends, "11": _forms,
            "12": _enhanced, "13": _start, "14": _exports, "15": _change_year}


def menu(principal: Principal) -> None:
    _state["actor"] = principal
    while True:
        activity_log.record("year6.open")
        print(f"\n  ── Year 6 Transition ({_year()} intake) ──")
        print("    1) Cohort\n    2) Sync from platform & admissions\n    3) Pupil details\n"
              "    4) Transition report\n    5) Edit details\n    6) Feeder schools\n"
              "    7) Liaison\n    8) Events\n    9) Invitations & attendance\n"
              "   10) Friendships & keep apart\n   11) Form allocation\n"
              "   12) Enhanced transition\n   13) Start in September\n   14) Exports\n"
              "   15) Change intake year\n    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except (*_ERRORS, OSError) as e:
            _problem(e)
        _pause()
