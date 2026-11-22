"""Academic Year & Calendar in the terminal. Rules live in
:mod:`modules.curriculum.domain.academic_year` and :mod:`modules.curriculum.domain.calendar_events`.
When editing, Enter keeps a value and ``-`` clears it."""

from __future__ import annotations

import calendar as _cal
import datetime as _dt

from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
from education_system.systems.secondary.modules.curriculum.domain import calendar_events as CE
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (AY.ValidationError, AY.PermissionDenied, AY.NotFound)


def _problem(e: Exception) -> None:
    prompts.problem(e, "Please fix:")


def _pick(options: list[str], label: str) -> str | None:
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    raw = _prompt(f"  {label}: ")
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    return None


def _date(prompt: str, default: _dt.date | None = None) -> _dt.date | None:
    raw = _prompt(f"  {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    if not raw:
        return default
    try:
        return _dt.date.fromisoformat(raw)
    except ValueError:
        print("  Use YYYY-MM-DD.")
        return None


def _choose_year() -> AY.AcademicYear | None:
    years = AY.list_years()
    if not years:
        print("\n  No academic years yet - add one first (Years).")
        return None
    cur = AY.current_year()
    print()
    for i, y in enumerate(years, 1):
        print(f"    {i}) {y.name} ({y.status})" + ("  ← current" if cur and
                                                    cur.year_id == y.year_id else ""))
    raw = _prompt(f"  Year [{cur.name if cur else years[0].name}]: ")
    if not raw:
        return cur or years[0]
    if raw.isdigit() and 1 <= int(raw) <= len(years):
        return years[int(raw) - 1]
    return None


# ── Menu ─────────────────────────────────────────────────────────────

def menu(principal: Principal) -> None:
    activity_log.record("calendar.open")
    while True:
        today = _dt.date.today()
        print(f"\n── Academic Year & Calendar ── today: {AY.day_info(today).label}")
        print("  1) Overview")
        print("  2) Years")
        print("  3) Terms")
        print("  4) Breaks (holidays, half-terms, INSET, bank holidays)")
        print("  5) Month view")
        print("  6) Day / look up a date")
        print("  7) Events")
        print("  8) Events summary")
        print("  0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", "", "q"}:
            return
        handler = {"1": overview, "2": years, "3": terms, "4": breaks, "5": month,
                   "6": day, "7": events, "8": summary}.get(choice)
        if handler:
            handler(principal)


def overview(principal: Principal) -> None:
    today = _dt.date.today()
    y = AY.current_year(today)
    if y is None:
        print("\n  No academic year is set up yet - add one in Years.")
        _pause()
        return
    check = AY.check_year(y.year_id)
    print(f"\n── {y.name} ({y.status}) ──")
    print(f"  Today: {AY.day_info(today).label}")
    print(f"  Pupil days: {check.pupil_days} (still to go: "
          f"{AY.school_days_between(today, AY._d(y.end_date))}) · INSET: {check.inset_days}")
    for t in AY.list_terms(y.year_id):
        print(f"  {t.name:<10} {t.start_date} to {t.end_date}")
    print("  Coming up:")
    for b in AY.upcoming_breaks(today):
        print(f"    {b.start_date}  {b.type}: {b.name}")
    for p in check.errors:
        print(f"  ✗ {p}")
    for p in check.warnings:
        print(f"  ⚠ {p}")
    _pause()


# ── Years ────────────────────────────────────────────────────────────

def years(principal: Principal) -> None:
    while True:
        rows = AY.list_years()
        print("\n── Years ──")
        for i, y in enumerate(rows, 1):
            print(f"  {i:>2}) {y.name}  {y.start_date} to {y.end_date}  {y.status:<9} "
                  f"terms {len(AY.list_terms(y.year_id))}  pupil days "
                  f"{AY.check_year(y.year_id).pupil_days}")
        print("\n  N) New   E) Edit   C) Set current   D) Delete   0) Back")
        choice = _prompt("Select: ").lower()
        if choice in {"0", "", "q"}:
            return
        try:
            if choice == "n":
                name = _prompt("  Name (e.g. 2027/28): ")
                y = AY.create_year(name, actor=principal,
                                   notes=_prompt("  Notes (optional): ") or None)
                print(f"  ✓ {y.name} added ({y.start_date} to {y.end_date}). Add its terms next.")
                continue
            if choice not in {"e", "c", "d"}:
                continue
            raw = _prompt("  Which (number): ")
            if not (raw.isdigit() and 1 <= int(raw) <= len(rows)):
                continue
            y = rows[int(raw) - 1]
            if choice == "e":
                status = None
                if y.status != "Active":
                    status = _pick(["Planning", "Archived"], f"Status [{y.status}]") or y.status
                notes = _ask("Notes", y.notes)
                AY.update_year(y.year_id, actor=principal, status=status,
                               notes=notes if notes is not None else None)
                print("  ✓ Saved.")
            elif choice == "c":
                AY.set_current(y.year_id, actor=principal)
                print(f"  ✓ {y.name} is now the current year.")
            elif choice == "d" and _yes(f"  Delete {y.name} with its terms and breaks?"):
                AY.delete_year(y.year_id, actor=principal)
                print("  ✓ Deleted.")
        except _ERRORS as e:
            _problem(e)


# ── Terms / breaks ───────────────────────────────────────────────────

def terms(principal: Principal) -> None:
    y = _choose_year()
    if y is None:
        return
    while True:
        rows = AY.list_terms(y.year_id)
        print(f"\n── Terms {y.name} ──" + ("  (archived: read only)" if y.locked else ""))
        for i, t in enumerate(rows, 1):
            print(f"  {i:>2}) {t.name:<10} {t.start_date} to {t.end_date}  {t.notes or ''}")
        print("\n  N) New   E) Edit   D) Delete   C) Copy from another year   0) Back")
        choice = _prompt("Select: ").lower()
        if choice in {"0", "", "q"}:
            return
        try:
            if choice == "n":
                name = _pick(list(AY.TERM_NAMES), "Term")
                data = {"name": name, "start_date": _prompt("  Start (YYYY-MM-DD): "),
                        "end_date": _prompt("  End (YYYY-MM-DD): "),
                        "notes": _prompt("  Notes (optional): ")}
                AY.add_term(y.year_id, data, actor=principal)
                print("  ✓ Added.")
            elif choice in {"e", "d"}:
                raw = _prompt("  Which (number): ")
                if not (raw.isdigit() and 1 <= int(raw) <= len(rows)):
                    continue
                t = rows[int(raw) - 1]
                if choice == "d":
                    if _yes(f"  Delete {t.name}?"):
                        AY.delete_term(t.term_id, actor=principal)
                    continue
                changes = {}
                for key, label in (("start_date", "Start"), ("end_date", "End"),
                                   ("notes", "Notes")):
                    v = _ask(label, getattr(t, key))
                    if v is not None:
                        changes[key] = v
                AY.update_term(t.term_id, changes, actor=principal)
                print("  ✓ Saved.")
            elif choice == "c":
                others = [o for o in AY.list_years() if o.year_id != y.year_id]
                src = _pick([o.name for o in others], "Copy from")
                if src:
                    t, b = AY.copy_from(y.year_id, next(o.year_id for o in others
                                                        if o.name == src), actor=principal)
                    print(f"  ✓ {t} terms and {b} breaks copied (moved by whole weeks). "
                          "Check every date.")
        except _ERRORS as e:
            _problem(e)


def breaks(principal: Principal) -> None:
    y = _choose_year()
    if y is None:
        return
    while True:
        rows = AY.list_breaks(y.year_id)
        print(f"\n── Breaks {y.name} ──" + ("  (archived: read only)" if y.locked else ""))
        for i, b in enumerate(rows, 1):
            span = b.start_date if b.start_date == b.end_date else \
                f"{b.start_date} to {b.end_date}"
            print(f"  {i:>2}) {b.type:<12} {span:<24} {b.name}")
        print("\n  N) New   E) Edit   D) Delete   B) Add bank holidays   0) Back")
        choice = _prompt("Select: ").lower()
        if choice in {"0", "", "q"}:
            return
        try:
            if choice == "n":
                type_ = _pick(list(AY.BREAK_TYPES), "Type")
                data = {"name": _prompt("  Name: "), "type": type_,
                        "start_date": _prompt("  Start (YYYY-MM-DD): "),
                        "end_date": _prompt("  End (Enter for one day): "),
                        "notes": _prompt("  Notes (optional): ")}
                AY.add_break(y.year_id, data, actor=principal)
                print("  ✓ Added.")
            elif choice == "b":
                added = AY.add_bank_holidays(y.year_id, actor=principal)
                print(f"  ✓ {len(added)} added.")
                for b in added:
                    print(f"     {b.start_date} {b.name}")
            elif choice in {"e", "d"}:
                raw = _prompt("  Which (number): ")
                if not (raw.isdigit() and 1 <= int(raw) <= len(rows)):
                    continue
                b = rows[int(raw) - 1]
                if choice == "d":
                    if _yes(f"  Delete {b.name}?"):
                        AY.delete_break(b.break_id, actor=principal)
                    continue
                changes = {}
                for key, label in (("name", "Name"), ("start_date", "Start"),
                                   ("end_date", "End"), ("notes", "Notes")):
                    v = _ask(label, getattr(b, key))
                    if v is not None:
                        changes[key] = v
                AY.update_break(b.break_id, changes, actor=principal)
                print("  ✓ Saved.")
        except _ERRORS as e:
            _problem(e)


# ── Month / day ──────────────────────────────────────────────────────

_MARK = {"school": "  ", "weekend": " ·", "closure": " x", "inset": " i", "holiday": " h",
         "none": " ?"}


def month(principal: Principal) -> None:
    today = _dt.date.today()
    y, m = today.year, today.month
    while True:
        days = AY.month_info(y, m)
        counts = CE.counts_by_day(min(days), max(days))
        print(f"\n── {_cal.month_name[m]} {y} ──   (x closed, i INSET, h holiday, · weekend, "
              "* events)")
        print("   Mon   Tue   Wed   Thu   Fri   Sat   Sun")
        line = "      " * min(days).weekday()
        for d, info in sorted(days.items()):
            if info.is_weekend:
                kind = "weekend"
            elif info.year is None:
                kind = "none"
            elif info.closure:
                kind = "inset" if info.closure.type == "INSET" else "closure"
            elif info.term is None:
                kind = "holiday"
            else:
                kind = "school"
            line += f"{d.day:>3}{_MARK[kind].strip() or ' '}{'*' if counts.get(d) else ' '} "
            if d.weekday() == 6:
                print(line)
                line = ""
        if line:
            print(line)
        choice = _prompt("\n  P) Previous  N) Next  D) Open a day  0) Back: ").lower()
        if choice == "p":
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        elif choice == "n":
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        elif choice == "d":
            raw = _prompt("  Day of month: ")
            if raw.isdigit() and 1 <= int(raw) <= max(days).day:
                day(principal, _dt.date(y, m, int(raw)))
        else:
            return


def day(principal: Principal, when: _dt.date | None = None) -> None:
    when = when or _date("Date (YYYY-MM-DD)", _dt.date.today())
    if when is None:
        return
    info = AY.day_info(when)
    activity_log.record("calendar.day", target=when.isoformat())
    print(f"\n── {when:%A %d %B %Y} ──")
    print(f"  {info.label}")
    print(f"  Academic year: {info.year.name if info.year else '— (not set up)'}")
    print(f"  Pupils in school: {'yes' if info.is_school_day else 'no'} · staff day: "
          f"{'yes' if info.is_staff_day else 'no'}")
    for b in info.breaks:
        print(f"  {b.type}: {b.name} ({b.start_date} to {b.end_date})")
    evs = CE.events_on(when)
    print(f"  Events ({len(evs)}):")
    for ev in evs:
        t = "all day" if ev.all_day else f"{ev.start_time or ''}-{ev.end_time or ''}"
        print(f"    #{ev.event_id:<4} {t:<12} {ev.title}  [{ev.event_type}, {ev.audience}, "
              f"{ev.status}]")
    _pause()


# ── Events ───────────────────────────────────────────────────────────

def _print_events(rows: list[CE.Event]) -> None:
    if not rows:
        print("\n  None.")
    for ev in rows:
        print(f"  #{ev.event_id:<4} {ev.when:<34} {ev.title[:30]:<30} {ev.event_type:<15} "
              f"{ev.audience:<8} {ev.status}")


def _event_data(ev: CE.Event | None) -> dict:
    out: dict = {}

    def ask(key: str, label: str, hint: str = "") -> None:
        v = _ask(label, None if ev is None else (None if getattr(ev, key) is None
                                                  else str(getattr(ev, key))), hint=hint)
        if v is not None:
            out[key] = v

    ask("title", "Title")
    print("  Type:")
    t = _pick(list(CE.EVENT_TYPES), f"Type{f' [{ev.event_type}]' if ev else ''}")
    if t:
        out["event_type"] = t
    ask("start_date", "Start date", "YYYY-MM-DD")
    ask("end_date", "End date", "Enter = same day" if ev is None else "")
    all_day = _ask("All day (y/n)", ("y" if ev.all_day else "n") if ev else "n")
    if all_day is not None:
        out["all_day"] = all_day
    if (all_day or ("y" if ev and ev.all_day else "n")).lower() not in {"y", "yes"}:
        ask("start_time", "Start time", "HH:MM")
        ask("end_time", "End time", "HH:MM")
    print("  Audience:")
    a = _pick(list(CE.AUDIENCES), f"Audience [{ev.audience if ev else 'All'}]")
    if a:
        out["audience"] = a
    for key, label in (("location", "Location"), ("organiser", "Organiser"),
                       ("capacity", "Capacity"), ("cost", "Cost (£)"),
                       ("description", "Description"), ("notes", "Notes")):
        ask(key, label)
    return out


def events(principal: Principal) -> None:
    today = _dt.date.today()
    start, end = today.isoformat(), (today + _dt.timedelta(days=30)).isoformat()
    while True:
        rows = CE.list_events(start=start, end=end)
        print(f"\n── Events {start or 'any'} to {end or 'any'} ──")
        _print_events(rows)
        print("\n  V) View  N) New  E) Edit  S) Status  C) Cancel  M) Complete  D) Delete")
        print("  R) Change date range  T) This term  0) Back")
        choice = _prompt("Select: ").lower()
        if choice in {"0", "", "q"}:
            return
        try:
            if choice == "r":
                start = _prompt("  From (YYYY-MM-DD, Enter for any): ") or ""
                end = _prompt("  To (YYYY-MM-DD, Enter for any): ") or ""
                continue
            if choice == "t":
                term = AY.term_for(today)
                if term:
                    start, end = term.start_date, term.end_date
                else:
                    print("  Today isn't in a term.")
                continue
            if choice == "n":
                data = _event_data(None)
                notes = CE.warnings_for(data.get("start_date", ""), data.get("end_date") or None)
                if notes and not _yes("  School isn't open on: " + "; ".join(notes[:5])
                                      + ". Save anyway?"):
                    continue
                ev = CE.create_event(data, actor=principal)
                print(f"  ✓ Added #{ev.event_id}.")
                continue
            if choice not in set("vescmd"):
                continue
            raw = _prompt("  Event number (#): ").lstrip("#")
            ev = CE.get_event(int(raw)) if raw.isdigit() else None
            if ev is None:
                print("  Not found.")
                continue
            if choice == "v":
                for k in ("title", "event_type", "when", "location", "organiser", "audience",
                          "status", "status_reason", "capacity", "cost", "description",
                          "notes", "created_by"):
                    v = getattr(ev, k)
                    if v not in (None, ""):
                        print(f"  {k.replace('_', ' ').capitalize()}: {v}")
                for w in CE.warnings_for(ev.start_date, ev.end_date):
                    print(f"  ⚠ {w}")
                _pause()
            elif choice == "e":
                CE.update_event(ev.event_id, _event_data(ev), actor=principal)
                print("  ✓ Saved.")
            elif choice == "s":
                new = _pick([s for s in CE.STATUSES if s != ev.status], "New status")
                if new:
                    CE.set_status(ev.event_id, new, actor=principal,
                                  reason=_prompt("  Reason: ") or None)
                    print("  ✓ Status changed.")
            elif choice == "c":
                CE.cancel_event(ev.event_id, actor=principal, reason=_prompt("  Reason *: "))
                print("  ✓ Cancelled.")
            elif choice == "m":
                CE.complete_event(ev.event_id, actor=principal)
                print("  ✓ Completed.")
            elif choice == "d" and _yes("  Delete it? (to call it off, Cancel instead)"):
                CE.delete_event(ev.event_id, actor=principal)
                print("  ✓ Deleted.")
        except _ERRORS as e:
            _problem(e)


def summary(principal: Principal) -> None:
    raw = _prompt("  Upcoming window in days [14]: ")
    days = int(raw) if raw.isdigit() and int(raw) > 0 else 14
    s = CE.summary(days=days)
    print(f"\n── Events summary ── {s.total} in all")
    print("  By type: " + ", ".join(f"{k} {n}" for k, n in s.by_type.items()))
    print("  By status: " + ", ".join(f"{k} {n}" for k, n in s.by_status.items()))
    print(f"  Next {days} days:")
    _print_events(s.upcoming)
    _pause()
