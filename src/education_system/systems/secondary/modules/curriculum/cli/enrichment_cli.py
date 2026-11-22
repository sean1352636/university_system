"""Enrichment & Clubs in the terminal. The old options 1-10 are kept (new club,
list, edit, toggle active, club summary + memberships, pupil club history, add
a pupil, set membership status, delete a membership, delete a club); 11-18 are
added. Rules live in :mod:`modules.curriculum.domain.enrichment`."""

from __future__ import annotations

import datetime as _dt

from education_system.systems.secondary.modules.curriculum.domain import enrichment as EN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (EN.ValidationError, EN.PermissionDenied, EN.NotFound)


_problem = prompts.problem


def _warn(warnings: list[str]) -> None:
    for w in warnings:
        print(f"  ! {w}")


def _pct(v) -> str:
    return "-" if v is None else f"{v}%"


def _print(rows: list[EN.Club]) -> None:
    if not rows:
        print("  (no clubs)")
        return
    print(f"  {'ID':<4} {'Name':<24} {'Category':<9} {'Day':<4} {'Time':<12} {'Room':<8} "
          f"{'Leader':<16} {'Cap':<4} {'Years':<12} {'Act':<4} Members")
    for c in rows:
        print(f"  {c.club_id:<4} {c.name[:24]:<24} {c.category:<9} {(c.day_of_week or ''):<4} "
              f"{c.time_label:<12} {(c.room or '')[:8]:<8} {(c.leader or '')[:16]:<16} "
              f"{str(c.max_capacity or ''):<4} {c.years_label[:12]:<12} "
              f"{'Yes' if c.is_active else 'No':<4} {c.active_members}"
              + (f" (+{c.waiting} waiting)" if c.waiting else ""))


def _print_members(club: EN.Club, rows: list[EN.Member]) -> None:
    if not rows:
        print("  (no members)")
        return
    att = EN.member_attendance(club.club_id)
    print(f"  {'ID':<5} {'Pupil':<24} {'Yr':<3} {'Form':<6} {'Joined':<10} {'Status':<11} "
          f"{'Consent':<10} {'Att':<6} Notes")
    for m in rows:
        consent = (m.consent_on or "needed") if club.consent_required else ""
        print(f"  {m.member_id:<5} {m.pupil_name[:24]:<24} {m.year_group:<3} "
              f"{(m.form_group or '')[:6]:<6} {m.joined_on:<10} {m.status:<11} {consent:<10} "
              f"{_pct(att.get(m.pupil_id, {}).get('pct')):<6} {(m.notes or '')[:30]}")


def _choose() -> EN.Club | None:
    raw = _prompt("  Club ID (or part of the name): ")
    if not raw:
        return None
    if raw.isdigit():
        try:
            return EN.get_club(int(raw))
        except EN.NotFound:
            print("  No such club.")
            return None
    hits = EN.list_clubs(search=raw)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        print("  No club matches.")
    else:
        _print(hits)
        print("  More than one club matches - use the ID.")
    return None


def _choose_pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil (admission no or UPN): ")
    if not ref:
        return None
    p = P.find_by_reference(ref)
    if p is None:
        print("  No pupil with that admission number or UPN.")
    return p


def _choose_member(club: EN.Club) -> EN.Member | None:
    _print_members(club, EN.list_members(club.club_id))
    raw = _prompt("  Membership ID (or admission no): ")
    if not raw:
        return None
    for m in EN.list_members(club.club_id):
        if raw == str(m.member_id) or raw.upper() == m.admission_no:
            return m
    print("  Not a member of this club.")
    return None


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("clubs.view")
        o = EN.overview()
        mine = EN.my_clubs(principal)
        print("\n── Enrichment & Clubs ──")
        print(f"  Clubs: {o['total']}   active: {o['active']}   active memberships: "
              f"{o['active_memberships']}   waiting: {o['waiting']}"
              + (f"   · you lead {len(mine)}" if mine else ""))
        print("   1) New club\n   2) List clubs\n   3) Edit club\n   4) Toggle club active"
              "\n   5) Club summary + memberships\n   6) Pupil club history"
              "\n   7) Add pupil to a club\n   8) Set membership status"
              "\n   9) Delete membership\n  10) Delete club"
              "\n  11) Take a register\n  12) Record parental consent"
              "\n  13) Cancel a meeting\n  14) E-mail a club's families"
              "\n  15) Clubs timetable\n  16) Participation report"
              "\n  17) Export a club list (CSV)\n  18) Club history\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        try:
            {"1": lambda: _new(principal), "2": _list, "3": lambda: _edit(principal),
             "4": lambda: _toggle(principal), "5": _summary, "6": _pupil_history,
             "7": lambda: _join(principal), "8": lambda: _status(principal),
             "9": lambda: _delete_member(principal), "10": lambda: _delete(principal),
             "11": lambda: _register(principal), "12": lambda: _consent(principal),
             "13": lambda: _cancel(principal), "14": lambda: _email(principal),
             "15": _timetable, "16": _participation, "17": lambda: _export(principal),
             "18": _history,
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


def _collect(existing: EN.Club | None) -> dict:
    data: dict = {}

    def ask(key: str, label: str, current=None, **kw) -> None:
        v = _ask(label, None if current in (None, "") else str(current), **kw)
        if v is not None:
            data[key] = v
    g = (lambda k: getattr(existing, k)) if existing else (lambda _k: None)
    ask("name", "Name", g("name"), required=existing is None)
    ask("category", "Category", g("category"), hint="/".join(EN.CATEGORIES))
    ask("description", "Description", g("description"))
    ask("day_of_week", "Day", g("day_of_week"), hint="/".join(EN.DAYS))
    ask("start_time", "Start time", g("start_time"), hint="HH:MM")
    ask("end_time", "End time", g("end_time"), hint="HH:MM")
    ask("room", "Room", g("room"))
    ask("leader_username", "Leader's staff login", g("leader_username"),
        hint="lets them run the club")
    ask("leader", "Leader name", g("leader"), hint="blank = from the login")
    ask("max_capacity", "Max capacity", g("max_capacity"), hint="blank = no limit")
    ask("eligible_years", "Eligible years", g("eligible_years"), hint="e.g. 7,8 - blank = all")
    ask("consent_required", "Parental consent needed", "y" if existing and
        existing.consent_required else "n", hint="y/n")
    ask("cost", "Cost per term (£)", g("cost"), hint="blank = free")
    ask("starts_on", "Starts on", g("starts_on"), hint="YYYY-MM-DD, optional")
    ask("ends_on", "Ends on", g("ends_on"), hint="YYYY-MM-DD, optional")
    ask("notes", "Notes", g("notes"))
    print("  (Enter keeps a value, '-' clears it)")
    return data


def _new(principal: Principal) -> None:
    c = EN.create_club(_collect(None), actor=principal)
    print(f"  ✓ Created club #{c.club_id} {c.name}")


def _list() -> None:
    active = _yes("  Active only?")
    cat = _prompt("  Category (Enter = all): ") or None
    year = _prompt("  Open to year (Enter = all): ")
    _print(EN.list_clubs(active_only=active, category=cat.title() if cat else None,
                         year_group=int(year) if year.isdigit() else None))
    _pause()


def _edit(principal: Principal) -> None:
    c = _choose()
    if not c:
        return
    c = EN.update_club(c.club_id, _collect(c), actor=principal)
    print(f"  ✓ Saved {c.name}")


def _toggle(principal: Principal) -> None:
    c = _choose()
    if c:
        c = EN.toggle_active(c.club_id, actor=principal)
        print(f"  ✓ {c.name} is now {'active' if c.is_active else 'inactive'}")


def _summary() -> None:
    c = _choose()
    if not c:
        return
    s = EN.club_summary(c.club_id)
    print(f"\n  {c.name} ({c.category}, {c.when})" + (f" · {c.room}" if c.room else "")
          + (f" · {c.leader}" if c.leader else ""))
    print("  Members: " + " · ".join(f"{k} {v}" for k, v in s["by_status"].items()))
    print(f"  Capacity: {s['capacity'] or 'no limit'}   spaces: "
          f"{s['spaces'] if s['spaces'] is not None else '-'}   meetings: {s['meetings']}   "
          f"attendance: {_pct(s['attendance_pct'])}")
    if s["no_consent"]:
        print(f"  ! No consent yet: {', '.join(m.pupil_name for m in s['no_consent'])}")
    print()
    _print_members(c, EN.list_members(c.club_id))
    _pause()


def _pupil_history() -> None:
    p = _choose_pupil()
    if not p:
        return
    rows = EN.for_pupil(p.pupil_id)
    print(f"\n  {p.display_name} ({p.admission_no}):")
    if not rows:
        print("  (no clubs)")
    for m in rows:
        rate = EN.attendance_rate(m.club_id, m.pupil_id)
        print(f"  {m.club_name[:28]:<28} {m.status:<11} joined {m.joined_on}"
              + (f" · left {m.left_on}" if m.left_on else "")
              + (f" · attendance {rate}%" if rate is not None else ""))
    _pause()


def _join(principal: Principal) -> None:
    c = _choose()
    if not c:
        return
    while True:
        p = _choose_pupil()
        if not p:
            return
        consent = c.consent_required and _yes("  Parental consent received?")
        try:
            m, warns = EN.join(c.club_id, p.pupil_id, actor=principal, consent=consent)
        except _ERRORS as e:
            _problem(e)
            continue
        print(f"  ✓ {m.pupil_name}: {m.status}")
        _warn(warns)


def _status(principal: Principal) -> None:
    c = _choose()
    m = c and _choose_member(c)
    if not c or not m:
        return
    print(f"  {m.pupil_name} in {c.name} - current status: {m.status}")
    status = _prompt(f"  New status ({'/'.join(EN.STATUSES)}): ")
    if not status:
        return
    note = _prompt("  Reason / note: ") or None
    m, moved = EN.set_status(m.member_id, status, actor=principal, note=note)
    print(f"  ✓ {m.pupil_name} is now {m.status}")
    for x in moved:
        print(f"  ✓ Moved up from the waiting list: {x.pupil_name}")


def _delete_member(principal: Principal) -> None:
    c = _choose()
    m = c and _choose_member(c)
    if c and m and _yes(f"  Remove {m.pupil_name} from {c.name}?"):
        EN.delete_member(m.member_id, actor=principal)
        print("  ✓ Removed")


def _delete(principal: Principal) -> None:
    c = _choose()
    if c and _yes(f"  Delete {c.name} and its memberships?"):
        EN.delete_club(c.club_id, actor=principal)
        print("  ✓ Deleted")


def _date(prompt: str, default: _dt.date) -> _dt.date | None:
    raw = _prompt(f"  {prompt} [{default.isoformat()}]: ")
    try:
        return _dt.date.fromisoformat(raw) if raw else default
    except ValueError:
        print("  Enter the date as YYYY-MM-DD.")
        return None


def _register(principal: Principal) -> None:
    c = _choose()
    if not c:
        return
    today = _dt.date.today()
    last = today if not c.day_of_week else today - _dt.timedelta(
        days=(today.weekday() - EN.DAYS.index(c.day_of_week)) % 7)
    d = _date("Meeting date", last)
    if not d:
        return
    rows, meeting = EN.register(c.club_id, d)
    if meeting and meeting.cancelled:
        print(f"  That meeting was cancelled: {meeting.note}")
        return
    if not rows:
        print("  No members on that date.")
        return
    print("  For each pupil: P present, A absent, E excused (Enter = keep / Present)")
    marks: dict[int, str] = {}
    for m, mark in rows:
        default = mark or ("P" if not c.consent_required or m.has_consent else "A")
        raw = _prompt(f"  {m.pupil_name[:28]:<28} [{default}]: ").upper() or default
        marks[m.pupil_id] = raw
    meeting, warns = EN.save_register(c.club_id, d, marks, actor=principal)
    print(f"  ✓ Register saved for {d:%a %d %b}: "
          f"{sum(1 for v in marks.values() if v == 'P')} present")
    _warn(warns)


def _consent(principal: Principal) -> None:
    c = _choose()
    m = c and _choose_member(c)
    if not c or not m:
        return
    if m.has_consent:
        if _yes(f"  Consent recorded {m.consent_on}. Withdraw it?"):
            EN.record_consent(m.member_id, actor=principal, given=False)
            print("  ✓ Withdrawn")
        return
    d = _date("Consent received on", _dt.date.today())
    if d:
        EN.record_consent(m.member_id, actor=principal, on=d)
        print("  ✓ Consent recorded")


def _send(principal: Principal, c: EN.Club, subject: str, body: str) -> None:
    result = EN.notify_families(c.club_id, subject, body, actor=principal)
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    report = E.deliver(result.message_id, principal=principal)
    print(f"  ✓ E-mail to {result.recipients} contact(s) ({report.mode}): "
          + ", ".join(f"{k} {v}" for k, v in report.counts.items() if v))
    if result.pupils_without_email:
        print("  No e-mail address for: "
              + ", ".join(p.display_name for p in result.pupils_without_email))


def _cancel(principal: Principal) -> None:
    c = _choose()
    if not c:
        return
    today = _dt.date.today()
    nxt = today if not c.day_of_week else today + _dt.timedelta(
        days=(EN.DAYS.index(c.day_of_week) - today.weekday()) % 7)
    d = _date("Date to cancel", nxt)
    if not d:
        return
    reason = _prompt("  Reason: ")
    EN.cancel_meeting(c.club_id, d, reason, actor=principal)
    print(f"  ✓ {c.name} on {d:%a %d %b} cancelled")
    subject, body = EN.cancellation_text(c, d, reason)
    print("\n  " + body.replace("\n", "\n  "))
    if _yes("\n  E-mail this to the families?"):
        _send(principal, c, subject, body)


def _email(principal: Principal) -> None:
    c = _choose()
    if not c:
        return
    subject = _prompt(f"  Subject [{c.name}]: ") or c.name
    print("  Message ({contact_name} and {pupil_first_name} are filled in); end with a "
          "line containing just '.':")
    lines = []
    while True:
        line = _prompt("  ")
        if line == ".":
            break
        lines.append(line)
    if not any(lines):
        print("  Nothing to send.")
        return
    if _yes(f"  Send to the families of {c.name}'s members?"):
        _send(principal, c, subject, "\n".join(lines))


def _timetable() -> None:
    year = _prompt("  Open to year (Enter = all): ")
    tt = EN.timetable(year_group=int(year) if year.isdigit() else None)
    if not tt:
        print("  (no active clubs)")
    for day, clubs in tt.items():
        print(f"\n  {day}")
        for c in clubs:
            places = (f"{c.spaces} free" if c.spaces and c.spaces > 0
                      else "full" if c.spaces is not None else "open")
            print(f"    {c.time_label:<12} {c.name[:26]:<26} {(c.room or '')[:8]:<8} "
                  f"{(c.leader or '')[:16]:<16} {'Yr ' + c.years_label:<14} {places}")
    _pause()


def _participation() -> None:
    year = _prompt("  Year (Enter = all): ")
    r = EN.participation(year_group=int(year) if year.isdigit() else None)
    print(f"\n  {r['taking_part']} of {r['pupils']} pupils take part in a club "
          f"({_pct(r['all_pct'])})")
    print(f"  FSM pupils {_pct(r['fsm_pct'])} · SEN pupils {_pct(r['sen_pct'])}")
    print("  By year: " + " · ".join(f"Y{y} {_pct(v)}" for y, v in r["by_year"].items()))
    rows = r["not_in_a_club"]
    if rows and _yes(f"  List the {len(rows)} pupil(s) not in a club?"):
        for p in rows:
            print(f"  {p.admission_no:<10} {p.display_name[:28]:<28} Y{p.year_group} "
                  f"{p.form_group or '':<6}" + (" FSM" if p.fsm_eligible else "")
                  + (f" SEN {p.sen_status}" if p.sen_status != "N" else ""))
    _pause()


def _export(principal: Principal) -> None:
    c = _choose()
    if not c:
        return
    path = _prompt(f"  Save to [club-{c.club_id}-members.csv]: ") or \
        f"club-{c.club_id}-members.csv"
    try:
        n = EN.export_members(c.club_id, path, actor=principal)
    except OSError as e:
        print(f"  Couldn't save: {e}")
        return
    print(f"  ✓ Saved {n} pupil(s) to {path}")


def _history() -> None:
    c = _choose()
    if not c:
        return
    rows = EN.history(c.club_id)
    if not rows:
        print("  No changes yet.")
    for h in rows:
        print(f"  {h['at']}  {h['actor']:<14} {h['action']:<14} "
              + ", ".join(f"{k}: {v}" for k, v in h["detail"].items()))
    _pause()
