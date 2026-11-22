"""Cover in the terminal. The old options 1-8 are kept (new, list, view, edit,
assign, set status, daily load, delete); 9-15 are added, and 13 holds the old
Cover Agency menu (supply staff). Rules live in :mod:`modules.curriculum.domain.cover`."""

from __future__ import annotations

import datetime as _dt

from education_system.systems.secondary.modules.curriculum.domain import cover as CV
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.core.permissions.access import COVER_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_problem = prompts.problem


def _print(covers: list[CV.Cover]) -> None:
    if not covers:
        print("  (no cover)")
        return
    print(f"  {'ID':<5} {'Date':<11} {'P':<2} {'Group':<10} {'Subj':<6} {'Absent':<18} "
          f"{'Cover':<18} {'Room':<6} Status")
    for c in covers:
        print(f"  {c.cover_id:<5} {c.date:<11} {c.period:<2} {c.group_code[:10]:<10} "
              f"{(c.subject_code or '')[:6]:<6} {c.absent_name[:18]:<18} "
              f"{(c.cover_name or '-')[:18]:<18} {(c.room or '')[:6]:<6} {c.status}")


def _choose() -> CV.Cover | None:
    raw = _prompt("  Cover ID: ")
    if not raw.isdigit():
        return None
    try:
        return CV.get(int(raw))
    except CV.NotFound:
        print("  No such cover.")
        return None


def _ask_date(label: str = "Date") -> str:
    today = _dt.date.today().isoformat()
    return _prompt(f"  {label} (YYYY-MM-DD) [{today}]: ") or today


def menu(principal: Principal) -> None:
    editor = principal.role in COVER_EDITORS
    while True:
        activity_log.record("cover.view")
        today = CV.list_covers(date=_dt.date.today(), include_cancelled=False)
        pending = sum(1 for c in today if c.status == "Pending")
        print("\n── Cover ──")
        print(f"  Today: {len(today)} lesson(s) covered" + (f", {pending} unassigned"
                                                           if pending else ""))
        print("   1) New cover arrangement\n   2) List arrangements\n   3) View arrangement"
              "\n   4) Edit arrangement\n   5) Assign cover teacher\n   6) Set status"
              "\n   7) Daily load\n   8) Delete arrangement\n   9) Record an absence"
              "\n  10) Absences\n  11) My cover\n  12) Cover sheet for a day"
              "\n  13) Supply staff (Cover Agency)\n  14) E-mail the cover to whoever is "
              "covering\n  15) Weekly cover limit\n   0) Back")
        c = _prompt("Select: ")
        if c in {"0", ""}:
            return
        if c in {"1", "5", "8", "14"} and not editor:
            print("  Only the cover manager can do this.")
            continue
        try:
            {"1": lambda: _new(principal), "2": _list, "3": _view,
             "4": lambda: _edit(principal), "5": lambda: _assign(principal),
             "6": lambda: _status(principal), "7": _daily_load,
             "8": lambda: _delete(principal), "9": lambda: _absence(principal),
             "10": lambda: _absences(principal), "11": lambda: _mine(principal),
             "12": _sheet, "13": lambda: _supply(principal, editor),
             "14": lambda: _notify(principal), "15": lambda: _limit(principal, editor),
             }.get(c, lambda: print("  Invalid selection."))()
        except (CV.ValidationError, CV.PermissionDenied, CV.NotFound) as e:
            _problem(e)


def _new(principal: Principal) -> None:
    print("\n  ── New cover (one lesson) ──")
    g = TG.find(_prompt("  Teaching group code: "))
    if g is None:
        print("  No such group this year.")
        return
    c = CV.create({"date": _ask_date(), "period": _prompt("  Period: "), "group_id": g.group_id,
                   "absent_name": _prompt(f"  Absent teacher [{g.teacher_name or ''}]: ")
                   or g.teacher_name, "room": _prompt("  Room (Enter = usual): "),
                   "notes": _prompt("  Notes: ")}, actor=principal)
    print(f"  ✓ Cover #{c.cover_id}: {c.group_code} {c.when} (Pending)")


def _list() -> None:
    day = _prompt("  Date (YYYY-MM-DD, Enter = from today): ")
    st = _prompt(f"  Status ({'/'.join(CV.STATUSES)}, Enter = all): ").title()
    absent = _prompt("  Absent teacher (Enter = all): ")
    _print(CV.list_covers(date=day or None, date_from=None if day else _dt.date.today(),
                          status=st or None, absent=absent or None))
    _pause()


def _view() -> None:
    c = _choose()
    if c:
        print()
        print("  " + CV.details_text(c).replace("\n", "\n  "))
        print(f"\n  Status: {c.status} · cover: {c.cover_name or '-'}"
              + (f" · e-mailed {c.notified_at}" if c.notified_at else ""))
        if c.notes:
            print(f"  Notes: {c.notes}")
        _pause()


def _edit(principal: Principal) -> None:
    c = _choose()
    if not c:
        return
    editor = principal.role in COVER_EDITORS
    changes = {}
    keys = (("room", "Room"), ("notes", "Notes"), ("work_set", "Cover work")) if editor \
        else (("work_set", "Cover work"),)
    print("  Enter keeps a value, '-' clears it.")
    for key, label in keys:
        v = _ask(label, getattr(c, key))
        if v is not None:
            changes[key] = v
    CV.update(c.cover_id, changes, actor=principal)
    print("  ✓ Saved.")


def _assign(principal: Principal) -> None:
    c = _choose()
    if not c:
        return
    people = CV.available(c.date, c.period, cover_id=c.cover_id)
    print(f"\n  Free for {c.group_code} {c.when} (fewest covers this week first):")
    for i, p in enumerate(people, 1):
        print(f"   {i:>2}) {'⚠ ' if p.over_limit else ''}{p.label}")
    if not people:
        print("   Nobody is free - add supply staff (13).")
    raw = _prompt("  Number, or type a name: ")
    if not raw:
        return
    if raw.isdigit() and 1 <= int(raw) <= len(people):
        p = people[int(raw) - 1]
        c2, warnings = CV.assign(c.cover_id, actor=principal, username=p.username, name=p.name,
                                 supply_id=p.supply_id)
    else:
        c2, warnings = CV.assign(c.cover_id, actor=principal, name=raw)
    for w in warnings:
        print(f"  ⚠ {w}")
    print(f"  ✓ {c2.cover_name} is covering {c2.group_code} {c2.when}.")


def _status(principal: Principal) -> None:
    c = _choose()
    if not c:
        return
    print(f"  Current: {c.status}")
    for i, s in enumerate(CV.STATUSES, 1):
        print(f"   {i}) {s}")
    raw = _prompt("  New status: ")
    if not raw.isdigit() or not 1 <= int(raw) <= len(CV.STATUSES):
        return
    status = CV.STATUSES[int(raw) - 1]
    note = _prompt("  Why isn't it needed? ") if status == "Cancelled" else None
    print(f"  ✓ {CV.set_status(c.cover_id, status, actor=principal, note=note).status}")


def _daily_load() -> None:
    load = CV.daily_load(_ask_date())
    print(f"\n  {load['total']} lesson(s) covered, {load['unassigned']} unassigned")
    for who, n in load["by_cover"].items():
        print(f"   {who:<30} {n} slot(s)")
    _print(load["covers"])
    _pause()


def _delete(principal: Principal) -> None:
    c = _choose()
    if c and _yes(f"  Delete cover for {c.group_code} {c.when}?"):
        CV.delete(c.cover_id, actor=principal)
        print("  ✓ Deleted.")


def _absence(principal: Principal) -> None:
    print("\n  ── Record an absence (no medical details) ──")
    editor = principal.role in COVER_EDITORS
    who = _prompt("  Staff login (Enter = me): ") if editor else ""
    start = _ask_date("First day")
    end = _prompt(f"  Last day [{start}]: ") or start
    p_from = _prompt("  From period (Enter = all day): ")
    p_to = _prompt("  To period: ") if p_from else ""
    for i, r in enumerate(CV.REASONS, 1):
        print(f"   {i}) {r}")
    raw = _prompt("  Reason: ")
    reason = CV.REASONS[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(
        CV.REASONS) else raw
    a, n = CV.create_absence({"teacher_username": who or principal.username,
                              "start_date": start, "end_date": end,
                              "from_period": p_from or None, "to_period": p_to or None,
                              "reason": reason, "notes": _prompt("  Notes for cover: ")},
                             actor=principal)
    print(f"  ✓ {a.teacher_name} away {a.dates_label} ({a.periods_label}): {n} lesson(s) "
          "need cover.")


def _absences(principal: Principal) -> None:
    rows = CV.list_absences(date_from=_dt.date.today().isoformat())
    if not rows:
        print("  No absences from today.")
    for a in rows:
        covers = CV.list_covers(absence_id=a.absence_id)
        print(f"  #{a.absence_id:<4} {a.teacher_name[:22]:<22} {a.dates_label:<26} "
              f"{a.periods_label:<8} {a.reason:<18} cover {sum(c.is_open for c in covers)}"
              f"/{len(covers)}")
    c = _prompt("  E) Edit dates   C) Cancel absence   Enter) Back: ").lower()
    if c not in {"e", "c"}:
        return
    raw = _prompt("  Absence #: ")
    if not raw.isdigit():
        return
    a = CV.get_absence(int(raw))
    if c == "c":
        if _yes(f"  {a.teacher_name} is in after all - cancel their open cover?"):
            print(f"  ✓ Cancelled {CV.cancel_absence(a.absence_id, actor=principal)} "
                  "cover request(s).")
        return
    changes = {}
    for key, label in (("start_date", "First day"), ("end_date", "Last day"),
                       ("from_period", "From period"), ("to_period", "To period")):
        v = _ask(label, None if getattr(a, key) is None else str(getattr(a, key)))
        if v is not None:
            changes[key] = v or None
    _a, added, cancelled = CV.update_absence(a.absence_id, changes, actor=principal)
    print(f"  ✓ Saved: {added} lesson(s) added to cover, {cancelled} cancelled.")


def _mine(principal: Principal) -> None:
    doing = CV.my_cover(principal)
    print("\n  Cover I'm doing:")
    _print(doing)
    mine = CV.list_covers(absent=principal.username, date_from=_dt.date.today(),
                          include_cancelled=False)
    print("\n  Cover for my lessons:")
    _print(mine)
    c = _prompt("  C) Confirm one   D) Mark one done   W) Set work for one   Enter) Back: "
                ).lower()
    if c in {"c", "d"}:
        x = _choose()
        if x:
            CV.set_status(x.cover_id, "Confirmed" if c == "c" else "Completed",
                          actor=principal)
            print("  ✓ Done.")
    elif c == "w":
        x = _choose()
        if x:
            v = _ask("Cover work", x.work_set)
            if v is not None:
                CV.update(x.cover_id, {"work_set": v}, actor=principal)
                print("  ✓ Saved.")


def _sheet() -> None:
    print()
    print("  " + CV.cover_sheet(_ask_date()).replace("\n", "\n  "))
    _pause()


def _notify(principal: Principal) -> None:
    c = _choose()
    if not c:
        return
    mid = CV.notify(c.cover_id, actor=principal)
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    report = E.deliver(mid, principal=principal)
    print(f"  ✓ E-mail to {c.cover_name} ({report.mode}): "
          + ", ".join(f"{k} {v}" for k, v in report.counts.items() if v))


def _limit(principal: Principal, editor: bool) -> None:
    print(f"  Weekly cover limit: {CV.weekly_limit()}")
    if editor and _yes("  Change it?"):
        print(f"  ✓ Now {CV.set_weekly_limit(_prompt('  New limit: '), actor=principal)}.")


def _supply(principal: Principal, editor: bool) -> None:
    """The old Cover Agency menu."""
    while True:
        print("\n  ── Supply staff (Cover Agency) ──")
        print("    1) Add staff\n    2) List staff\n    3) Edit staff\n    4) Toggle active"
              "\n    5) Delete staff\n    6) New booking (assign to a cover request)"
              "\n    7) List bookings\n    8) Set booking status\n    9) Delete booking"
              "\n   10) Costs\n    0) Back")
        c = _prompt("  Select: ")
        if c in {"0", ""}:
            return
        if c in {"1", "3", "4", "5", "6", "8", "9"} and not editor:
            print("  Only the cover manager can do this.")
            continue
        try:
            if c == "1":
                s = CV.create_supply(_supply_fields(None), actor=principal)
                print(f"  ✓ Added {s.full_name}.")
            elif c == "2":
                for s in CV.list_supply():
                    print(f"  #{s.supply_id:<4} {s.full_name[:24]:<24} "
                          f"{(s.agency_name or '')[:18]:<18} {s.role:<18} "
                          f"{'£%.2f' % s.hourly_rate if s.hourly_rate is not None else '-':<8} "
                          f"DBS {'yes' if s.dbs_cleared else 'NO':<4} "
                          f"{'active' if s.is_active else 'inactive'}")
                _pause()
            elif c in {"3", "4", "5"}:
                raw = _prompt("  Supply #: ")
                if not raw.isdigit():
                    continue
                s = CV.get_supply(int(raw))
                if c == "3":
                    CV.update_supply(s.supply_id, _supply_fields(s), actor=principal)
                elif c == "4":
                    s = CV.toggle_supply(s.supply_id, actor=principal)
                    print(f"  ✓ {'Active' if s.is_active else 'Inactive'}.")
                    continue
                elif _yes(f"  Delete {s.full_name}?"):
                    CV.delete_supply(s.supply_id, actor=principal)
                print("  ✓ Done.")
            elif c == "6":
                x = _choose()
                if x:
                    raw = _prompt("  Supply #: ")
                    if raw.isdigit():
                        x2, _w = CV.assign(x.cover_id, actor=principal, supply_id=int(raw))
                        print(f"  ✓ {x2.cover_name} booked for {x2.group_code} {x2.when}.")
            elif c == "7":
                _print([x for x in CV.list_covers(date_from=_dt.date.today(),
                                                  include_cancelled=False) if x.supply_id])
                _pause()
            elif c == "8":
                _status(principal)
            elif c == "9":
                x = _choose()
                if x and x.supply_id and _yes("  Remove this booking (the lesson goes back "
                                              "to Pending)?"):
                    CV.unassign(x.cover_id, actor=principal)
                    print("  ✓ Removed.")
            elif c == "10":
                today = _dt.date.today()
                start = _prompt(f"  From [{today.replace(day=1)}]: ") or today.replace(day=1)
                end = _prompt(f"  To [{today}]: ") or today
                rows = CV.supply_report(start, end)
                for r in rows:
                    print(f"  {r['supply'].full_name:<24} {r['supply'].agency_name or '':<18} "
                          f"{r['periods']} period(s)  £{r['cost']:.2f}")
                print(f"  Total £{sum(r['cost'] for r in rows):.2f}")
                _pause()
            else:
                print("  Invalid selection.")
        except (CV.ValidationError, CV.PermissionDenied, CV.NotFound) as e:
            _problem(e)


def _supply_fields(s: CV.Supply | None) -> dict:
    data = {}
    for key, label in (("full_name", "Name"), ("agency_name", "Agency"),
                       ("role", f"Role ({' / '.join(CV.SUPPLY_ROLES)})"),
                       ("hourly_rate", "Hourly rate (£)"), ("email", "E-mail"),
                       ("phone", "Phone"), ("dbs_checked_on", "DBS seen on (YYYY-MM-DD)"),
                       ("notes", "Notes")):
        cur = getattr(s, key) if s else None
        v = _ask(label, None if cur is None else str(cur), required=key == "full_name"
                 and s is None)
        if v is not None:
            data[key] = v
    data["dbs_cleared"] = _yes("  DBS clearance seen?")
    return data
