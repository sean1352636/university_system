"""Alumni CLI: engagement & programmes, reports & analytics, operational quality.

Split out of ``alumni_cli`` (2026-10-22); that module re-exports every name.
"""

from __future__ import annotations

from ._helpers import (
    Any,
    CAMPAIGN_STATUSES,
    DEFAULT_CAMPAIGN_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_PLEDGE_STATUS,
    DEFAULT_RSVP_STATUS,
    DESTINATION_TYPES,
    EVENT_STATUSES,
    EVENT_TYPES,
    MENTORSHIP_STATUSES,
    PAYMENT_METHODS,
    PLEDGE_STATUSES,
    REFERENCE_TYPES,
    RSVP_STATUSES,
    SECTORS,
    SESSION_FORMATS,
    VOLUNTEER_ACTIVITY_TYPES,
    ValidationError,
    WORK_EXP_STATUSES,
    _UserAbort,
    _date,
)
from education_system.systems.sixth_form.domain.learners.alumni import (
    bulk_io as alumni_bulk_io,
    events as alumni_events,
    fundraising as alumni_fundraising,
    mentoring as alumni_mentoring,
    models as alumni_models,
    outcomes as alumni_outcomes,
    programmes as alumni_programmes,
    records as alumni_records,
    surveys as alumni_surveys,
)
from ._helpers import (  # noqa: F401
    _input,
    _pause,
    _pick_alumnus,
    _pick_from,
    _print_alumni,
    _yes_no,
)


# ── Engagement & programmes ───────────────────────────────────────

def _money_str(pence: int | None) -> str:
    if pence is None:
        return "—"
    return f"£{pence / 100:,.2f}"


def _pick_event() -> int:
    rows = alumni_events.list_events()
    if not rows:
        print("    (no events yet)")
        raise _UserAbort
    print("\n  Events:")
    for i, e in enumerate(rows, 1):
        print(f"    {i:>2}) #{e.event_id:<3} {e.name[:40]:<40} "
              f"{e.event_date or '—':<10}  [{e.status}]")
    raw = _input(f"Pick #1..{len(rows)} (or event id)",
                    allow_empty=False)
    n = int(raw) if raw.isdigit() else -1
    if 1 <= n <= len(rows):
        return rows[n - 1].event_id
    match = next((e for e in rows if e.event_id == n), None)
    if match is None:
        raise _UserAbort
    return match.event_id


def _pick_campaign() -> int:
    rows = alumni_fundraising.list_campaigns()
    if not rows:
        print("    (no campaigns yet)")
        raise _UserAbort
    print("\n  Campaigns:")
    for i, c in enumerate(rows, 1):
        print(f"    {i:>2}) #{c.campaign_id:<3} {c.name[:40]:<40} "
              f"[{c.status}]  target={_money_str(c.target_pence)}")
    raw = _input(f"Pick #1..{len(rows)} (or campaign id)",
                    allow_empty=False)
    n = int(raw) if raw.isdigit() else -1
    if 1 <= n <= len(rows):
        return rows[n - 1].campaign_id
    match = next((c for c in rows if c.campaign_id == n), None)
    if match is None:
        raise _UserAbort
    return match.campaign_id


def events_flow() -> None:
    print("\n═══ Events ═══")
    while True:
        rows = alumni_events.list_events()
        print(f"\n  {len(rows)} event(s):")
        for e in rows[:25]:
            print(f"    #{e.event_id:<3} {e.event_date or '—':<10} "
                  f"[{e.status:<10}] {e.event_type:<14} "
                  f"{e.name[:36]:<36}  cost={_money_str(e.cost_pence)}")
        print("\n    a) Add  e) Edit status  v) View RSVPs  "
               "r) Set RSVP  d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                alumni_events.create_event({
                    "name":       _input("Name", allow_empty=False),
                    "event_type": _pick_from("Type", list(EVENT_TYPES),
                                               default=EVENT_TYPES[0]),
                    "event_date": _input("Date (YYYY-MM-DD)"),
                    "location":   _input("Location"),
                    "capacity":   _input("Capacity") or None,
                    "cost":       _input("Cost in £") or 0,
                    "status":     _pick_from(
                        "Status", list(EVENT_STATUSES),
                        default=DEFAULT_EVENT_STATUS),
                    "notes":      _input("Notes"),
                })
            elif choice == "e":
                eid = int(_input("Event #id", allow_empty=False))
                new = _pick_from("New status", list(EVENT_STATUSES),
                                   default=DEFAULT_EVENT_STATUS)
                alumni_events.update_event(eid, {"status": new})
            elif choice == "v":
                eid = int(_input("Event #id", allow_empty=False))
                rsvps = alumni_events.list_rsvps_for_event(eid)
                att = alumni_events.event_attendance(eid)
                print(f"\n  {len(rsvps)} RSVP(s); invited={att.invited} "
                      f"accepted={att.accepted} declined={att.declined} "
                      f"attended={att.attended} (headcount {att.headcount})")
                for r in rsvps:
                    print(f"    rsvp #{r.rsvp_id:<3} alumnus #{r.alumni_id:<3} "
                          f"[{r.status:<10}] guests={r.guests} "
                          f"attended={'✓' if r.attended else ' '}")
                _pause()
            elif choice == "r":
                eid = int(_input("Event #id", allow_empty=False))
                a = _pick_alumnus()
                status = _pick_from("RSVP status",
                                       list(RSVP_STATUSES),
                                       default=DEFAULT_RSVP_STATUS)
                guests = int(_input("Guests", default="0") or 0)
                att = _yes_no("Attended?", default=False)
                alumni_events.set_rsvp(eid, a.alumni_id, status=status,
                                guests=guests, attended=att)
            elif choice == "d":
                eid = int(_input("Delete event #id",
                                    allow_empty=False))
                if _yes_no(f"Delete event #{eid} and all RSVPs?",
                             default=False):
                    alumni_events.delete_event(eid)
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def mentoring_flow() -> None:
    print("\n═══ Mentoring ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        mships = alumni_mentoring.list_mentorships_by_mentor(a.alumni_id)
        print(f"\n  Mentorships by #{a.alumni_id} {a.full_name}:")
        if not mships:
            print("    (none)")
        for m in mships:
            print(f"    #{m.mentorship_id:<3} mentee={m.mentee_student_id:<10} "
                  f"started {m.started_on}  [{m.status}]  "
                  f"{(m.topic or '')[:30]}")
        print("\n    s) Start  l) Sessions  ls) Log session  "
               "e) End  d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "s":
                sid = _input("Mentee student id", allow_empty=False)
                alumni_mentoring.start_mentorship(a.alumni_id, sid,
                                        topic=_input("Topic"),
                                        notes=_input("Notes"))
            elif choice == "l":
                mid = int(_input("Mentorship #id", allow_empty=False))
                sessions = alumni_mentoring.list_mentor_sessions(mid)
                if not sessions:
                    print("    (no sessions)")
                for s in sessions:
                    print(f"    sess #{s.session_id:<3} {s.session_date} "
                          f"{s.duration_minutes or 0}m "
                          f"{s.format or ''}  {(s.summary or '')[:40]}")
                _pause()
            elif choice == "ls":
                mid = int(_input("Mentorship #id", allow_empty=False))
                fmt = ""
                if _yes_no("Set format?", default=True):
                    fmt = _pick_from("Format", list(SESSION_FORMATS),
                                       default="Video")
                alumni_mentoring.log_mentor_session(mid, {
                    "session_date":     _input("Date (YYYY-MM-DD)",
                                                  default=_date.today().isoformat()),
                    "duration_minutes": _input("Duration (mins)"),
                    "format":           fmt,
                    "summary":          _input("Summary"),
                    "mentor_feedback":  _input("Mentor feedback"),
                    "mentee_feedback":  _input("Mentee feedback"),
                })
            elif choice == "e":
                mid = int(_input("Mentorship #id", allow_empty=False))
                new = _pick_from("Final status",
                                   list(MENTORSHIP_STATUSES),
                                   default="Completed")
                alumni_mentoring.end_mentorship(mid, status=new,
                                      notes=_input("Closing notes"))
            elif choice == "d":
                mid = int(_input("Mentorship #id", allow_empty=False))
                if _yes_no("Delete? Cascades sessions.",
                             default=False):
                    alumni_mentoring.delete_mentorship(mid)
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def speakers_flow() -> None:
    print("\n═══ Speaker Register ═══")
    print("  1) Browse register   2) Edit one alumnus's profile")
    try:
        which = _input("Choice", default="1")
        if which == "2":
            a = _pick_alumnus()
            cur = alumni_programmes.get_speaker(a.alumni_id)
            print(f"\n  Existing profile: {cur}")
            topics  = _input("Topics (comma-separated)",
                                default=(cur.topics or "") if cur else "")
            years   = _input("Year groups",
                                default=(cur.year_groups or "") if cur else "")
            avail   = _input("Availability notes",
                                default=(cur.availability_notes or "")
                                  if cur else "")
            confirm = _yes_no("Mark as confirmed today?", default=False)
            alumni_programmes.upsert_speaker(a.alumni_id, topics=topics,
                                  year_groups=years,
                                  availability_notes=avail,
                                  confirm=confirm)
            print("\n  ✓ Saved.")
        else:
            topic = _input("Filter: topic contains") or None
            yr    = _input("Filter: year group") or None
            rows = alumni_programmes.list_speakers(topic_like=topic, year_group=yr)
            print(f"\n  {len(rows)} speaker(s):")
            for s in rows:
                al = alumni_records.get_alumnus(s.alumni_id)
                if al:
                    print(f"    #{al.alumni_id:<3} {al.full_name:<26}  "
                          f"topics={(s.topics or '')[:30]}  "
                          f"years={(s.year_groups or '')[:12]}  "
                          f"confirmed={s.last_confirmed_at or '—'}")
    except _UserAbort:
        print("\n  Cancelled.")
    except ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def work_exp_flow() -> None:
    print("\n═══ Work-Experience Offers ═══")
    while True:
        rows = alumni_programmes.list_work_exp_offers()
        print(f"\n  {len(rows)} offer(s):")
        for o in rows[:25]:
            print(f"    #{o.offer_id:<3} alumnus #{o.alumni_id:<3} "
                  f"[{o.status:<8}] {o.title[:30]:<30} @ "
                  f"{(o.employer or '—')[:18]:<18} "
                  f"deadline={o.deadline or '—'}")
        print("\n    a) Add  v) Applicants  app) Apply (student)  "
               "s) Set offer status  ss) Set app status  "
               "d) Delete offer  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                al = _pick_alumnus()
                sector = ""
                if _yes_no("Set sector?", default=False):
                    sector = _pick_from("Sector", list(SECTORS),
                                          default=SECTORS[0])
                alumni_programmes.add_work_exp_offer(al.alumni_id, {
                    "title":          _input("Title",
                                                allow_empty=False),
                    "employer":       _input("Employer"),
                    "sector":         sector,
                    "location":       _input("Location"),
                    "duration_weeks": _input("Duration (weeks)"),
                    "start_window":   _input("Start window"),
                    "vacancy_count":  _input("Vacancies", default="1"),
                    "requirements":   _input("Requirements"),
                    "deadline":       _input("Deadline (YYYY-MM-DD)"),
                    "notes":          _input("Notes"),
                })
            elif choice == "v":
                oid = int(_input("Offer #id", allow_empty=False))
                apps = alumni_programmes.list_work_exp_applications(oid)
                print(f"\n  {len(apps)} application(s):")
                for ap in apps:
                    print(f"    app #{ap.application_id:<3} "
                          f"{ap.student_id:<10} {ap.applied_on}  "
                          f"[{ap.status}]")
                _pause()
            elif choice == "app":
                oid = int(_input("Offer #id", allow_empty=False))
                sid = _input("Student id", allow_empty=False)
                alumni_programmes.apply_to_work_exp(oid, sid)
            elif choice == "s":
                oid = int(_input("Offer #id", allow_empty=False))
                new = _pick_from("New status",
                                   list(WORK_EXP_STATUSES),
                                   default="Open")
                alumni_programmes.update_work_exp_status(oid, new)
            elif choice == "ss":
                aid = int(_input("Application #id",
                                    allow_empty=False))
                from education_system.systems.sixth_form.domain.learners.alumni.models import (
                    WORK_EXP_APP_STATUSES as _S,
                )
                new = _pick_from("New status", list(_S),
                                   default="Submitted")
                alumni_programmes.set_work_exp_application_status(
                    aid, new, notes=_input("Outcome notes"))
            elif choice == "d":
                oid = int(_input("Delete offer #id",
                                    allow_empty=False))
                if _yes_no("Delete? Cascades applications.",
                             default=False):
                    alumni_programmes.delete_work_exp_offer(oid)
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def references_flow() -> None:
    print("\n═══ References ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = alumni_programmes.list_references(a.alumni_id)
        print(f"\n  References for #{a.alumni_id} {a.full_name}:")
        if not rows:
            print("    (none)")
        for r in rows:
            print(f"    #{r.reference_id:<3} {r.ref_type:<9}  "
                  f"requested={r.requested_on or '—':<10} "
                  f"sent={r.sent_on or '—':<10}  "
                  f"{(r.target_name or '')[:30]}")
        print("\n    a) Add  m) Mark sent  d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                alumni_programmes.add_reference(a.alumni_id, {
                    "staff_id":     _input("Staff id (writer)"),
                    "ref_type":     _pick_from("Type",
                                                  list(REFERENCE_TYPES),
                                                  default="Job"),
                    "requested_on": _input("Requested on (YYYY-MM-DD)"),
                    "sent_on":      _input("Sent on (YYYY-MM-DD)"),
                    "target_name":  _input("Target (employer / "
                                              "institution)"),
                    "target_url":   _input("Target URL"),
                    "notes":        _input("Notes"),
                })
            elif choice == "m":
                rid = int(_input("Reference #id", allow_empty=False))
                alumni_programmes.mark_reference_sent(rid)
            elif choice == "d":
                rid = int(_input("Reference #id", allow_empty=False))
                if alumni_programmes.delete_reference(rid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def volunteering_flow() -> None:
    print("\n═══ Volunteering ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = alumni_programmes.list_volunteer_hours(a.alumni_id)
        total = alumni_programmes.total_volunteer_hours(a.alumni_id)
        print(f"\n  Volunteer log for #{a.alumni_id} {a.full_name} "
              f"(total {total:g}h):")
        if not rows:
            print("    (none)")
        for v in rows[:25]:
            ev = f" (event #{v.event_id})" if v.event_id else ""
            print(f"    #{v.volunteer_id:<3} {v.activity_date}  "
                  f"{v.hours:>5g}h  {v.activity_type:<18}{ev}")
        print("\n    a) Add  d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                attach_event = None
                if _yes_no("Attach to an event?", default=False):
                    attach_event = _pick_event()
                alumni_programmes.log_volunteer_hours(
                    a.alumni_id,
                    float(_input("Hours", allow_empty=False)),
                    activity_type=_pick_from(
                        "Activity", list(VOLUNTEER_ACTIVITY_TYPES),
                        default="Mock Interview"),
                    activity_date=_input(
                        "Date (YYYY-MM-DD)",
                        default=_date.today().isoformat()),
                    event_id=attach_event,
                    notes=_input("Notes"))
            elif choice == "d":
                vid = int(_input("Entry #id", allow_empty=False))
                if alumni_programmes.delete_volunteer_entry(vid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def campaigns_flow() -> None:
    print("\n═══ Fundraising Campaigns ═══")
    while True:
        rows = alumni_fundraising.list_campaigns()
        print(f"\n  {len(rows)} campaign(s):")
        for c in rows:
            t = alumni_fundraising.campaign_totals(c.campaign_id)
            print(f"    #{c.campaign_id:<3} [{c.status:<8}] "
                  f"{c.name[:30]:<30}  raised={_money_str(t.raised_pence)} "
                  f"pledged_open={_money_str(t.pledged_open_pence)} "
                  f"target={_money_str(c.target_pence)}")
        print("\n    a) Add  s) Set status  d) Delete  v) View "
               "donations  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                alumni_fundraising.create_campaign({
                    "name":        _input("Name", allow_empty=False),
                    "description": _input("Description"),
                    "target":      _input("Target in £"),
                    "start_on":    _input("Start (YYYY-MM-DD)"),
                    "end_on":      _input("End (YYYY-MM-DD)"),
                    "status":      _pick_from(
                        "Status", list(CAMPAIGN_STATUSES),
                        default=DEFAULT_CAMPAIGN_STATUS),
                })
            elif choice == "s":
                cid = int(_input("Campaign #id", allow_empty=False))
                new = _pick_from("New status",
                                   list(CAMPAIGN_STATUSES),
                                   default=DEFAULT_CAMPAIGN_STATUS)
                alumni_fundraising.update_campaign_status(cid, new)
            elif choice == "d":
                cid = int(_input("Campaign #id", allow_empty=False))
                if _yes_no("Delete? Donations/pledges keep their "
                             "history but lose the campaign link.",
                             default=False):
                    alumni_fundraising.delete_campaign(cid)
            elif choice == "v":
                cid = int(_input("Campaign #id", allow_empty=False))
                dons = alumni_fundraising.list_donations(campaign_id=cid)
                print(f"\n  {len(dons)} donation(s):")
                for d in dons:
                    print(f"    #{d.donation_id:<4} {d.donation_date} "
                          f"alumnus #{d.alumni_id:<3} "
                          f"{_money_str(d.amount_pence):>10} "
                          f"{'GA' if d.gift_aid else '  '} "
                          f"{(d.payment_method or '—')[:14]:<14}")
                pls = alumni_fundraising.list_pledges(campaign_id=cid)
                print(f"\n  {len(pls)} pledge(s):")
                for p in pls:
                    print(f"    #{p.pledge_id:<4} {p.pledged_on} "
                          f"alumnus #{p.alumni_id:<3} "
                          f"{_money_str(p.amount_pence):>10} "
                          f"[{p.status}]")
                _pause()
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def donations_flow() -> None:
    print("\n═══ Donations & Pledges ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        dons = alumni_fundraising.list_donations(alumni_id=a.alumni_id)
        pls  = alumni_fundraising.list_pledges(alumni_id=a.alumni_id)
        print(f"\n  For #{a.alumni_id} {a.full_name}:")
        print(f"\n  Donations ({len(dons)}):")
        for d in dons[:15]:
            print(f"    #{d.donation_id:<4} {d.donation_date} "
                  f"{_money_str(d.amount_pence):>10}  "
                  f"campaign #{d.campaign_id or '—':<3}  "
                  f"{'GA' if d.gift_aid else '  '} "
                  f"{(d.payment_method or '—')}")
        print(f"\n  Pledges ({len(pls)}):")
        for p in pls[:15]:
            print(f"    #{p.pledge_id:<4} {p.pledged_on} "
                  f"{_money_str(p.amount_pence):>10}  "
                  f"campaign #{p.campaign_id or '—':<3}  "
                  f"[{p.status}]  due={p.due_by or '—'}")
        print("\n    d) Add donation   p) Add pledge   "
               "sp) Set pledge status   xd) Delete donation   "
               "xp) Delete pledge   0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            cid = None
            if choice in ("d", "p"):
                if _yes_no("Attach to a campaign?", default=True):
                    cid = _pick_campaign()
            if choice == "d":
                method = ""
                if _yes_no("Set payment method?", default=True):
                    method = _pick_from(
                        "Payment method", list(PAYMENT_METHODS),
                        default="Card")
                alumni_fundraising.record_donation(a.alumni_id, {
                    "amount":         _input("Amount in £",
                                                allow_empty=False),
                    "campaign_id":    cid,
                    "donation_date":  _input(
                        "Date (YYYY-MM-DD)",
                        default=_date.today().isoformat()),
                    "gift_aid":       _yes_no("Gift Aid?",
                                                default=False),
                    "payment_method": method,
                    "anonymous":      _yes_no("Anonymous?",
                                                default=False),
                    "restricted_to":  _input("Restricted to (purpose)"),
                    "notes":          _input("Notes"),
                })
            elif choice == "p":
                alumni_fundraising.add_pledge(a.alumni_id, {
                    "amount":      _input("Pledge amount in £",
                                             allow_empty=False),
                    "campaign_id": cid,
                    "pledged_on":  _input(
                        "Pledged on (YYYY-MM-DD)",
                        default=_date.today().isoformat()),
                    "due_by":      _input("Due by (YYYY-MM-DD)"),
                    "status":      _pick_from(
                        "Status", list(PLEDGE_STATUSES),
                        default=DEFAULT_PLEDGE_STATUS),
                    "notes":       _input("Notes"),
                })
            elif choice == "sp":
                pid = int(_input("Pledge #id", allow_empty=False))
                new = _pick_from("New status", list(PLEDGE_STATUSES),
                                   default=DEFAULT_PLEDGE_STATUS)
                alumni_fundraising.update_pledge_status(pid, new)
            elif choice == "xd":
                did = int(_input("Donation #id", allow_empty=False))
                if _yes_no("Delete donation? Irreversible.",
                             default=False):
                    alumni_fundraising.delete_donation(did)
            elif choice == "xp":
                pid = int(_input("Pledge #id", allow_empty=False))
                if alumni_fundraising.delete_pledge(pid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


# ── Reports & analytics ───────────────────────────────────────────

def _ask_year(label: str = "Leaving year (YYYY)") -> str:
    raw = _input(label, allow_empty=False)
    return raw


def report_ks5_csv() -> None:
    print("\n═══ DfE KS5 Destinations CSV ═══")
    try:
        year = _ask_year()
        path = _input("Output path (blank to print)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        result = alumni_outcomes.ks5_destinations_csv(
            leaving_year=year, out_path=path or None)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if path:
        print(f"\n  ✓ Wrote {result}")
    else:
        print("\n" + result)
    _pause()


def report_sustained() -> None:
    print("\n═══ Sustained Destinations (1y / 3y / 5y) ═══")
    try:
        year = _ask_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = alumni_outcomes.sustained_destinations(leaving_year=year)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  Cohort of {year}:")
    print(f"  {'#':>4}  {'Name':<26}  {'+1y':<14} {'+3y':<14} {'+5y':<14}")
    print("  " + "-" * 80)
    for r in rows:
        print(f"  {r.alumni_id:>4}  {r.full_name[:26]:<26}  "
              f"{r.year_plus_1:<14} {r.year_plus_3:<14} "
              f"{r.year_plus_5:<14}")
    _pause()


def report_cohort_comparison() -> None:
    print("\n═══ Cohort Comparison ═══")
    cc = alumni_outcomes.cohort_comparison()
    if not cc.years:
        print("\n  (no data)")
        _pause()
        return
    # column widths
    cw = max(len(d) for d in cc.destinations) + 2
    header = "  Year  Total  " + "  ".join(
        f"{d[:cw]:<{cw}}" for d in cc.destinations)
    print()
    print(header)
    print("  " + "-" * (len(header) - 2))
    for y in cc.years:
        cells = []
        for d in cc.destinations:
            n = cc.counts.get(y, {}).get(d, 0)
            cells.append(f"{n:<{cw}}")
        print(f"  {y}  {cc.totals[y]:>5}  " + "  ".join(cells))
    _pause()


def report_university_success() -> None:
    print("\n═══ University Success Rates ═══")
    rows = alumni_outcomes.university_success_rates()
    if not rows:
        print("\n  (no university destinations)")
        _pause()
        return
    print(f"\n  {'Year':<6} {'Total':>6} {'Russell':>8} "
          f"{'Oxbridge':>9} {'TopThird':>9}")
    print("  " + "-" * 45)
    for r in rows:
        rp = 100 * r.russell / r.uni_total if r.uni_total else 0
        op = 100 * r.oxbridge / r.uni_total if r.uni_total else 0
        tp = 100 * r.top_third / r.uni_total if r.uni_total else 0
        print(f"  {r.leaving_year:<6} {r.uni_total:>6} "
              f"{r.russell:>3} ({rp:>3.0f}%) "
              f"{r.oxbridge:>3} ({op:>3.0f}%) "
              f"{r.top_third:>3} ({tp:>3.0f}%)")
    _pause()


def report_apprenticeship_outcomes() -> None:
    print("\n═══ Apprenticeship Outcomes ═══")
    rows = alumni_outcomes.apprenticeship_outcomes()
    if not rows:
        print("\n  (no apprenticeship destinations)")
        _pause()
        return
    print(f"\n  {'Year':<6} {'Level':<10} {'Provider':<40} {'#':>3}")
    print("  " + "-" * 64)
    for r in rows:
        print(f"  {r.leaving_year:<6} {r.level:<10} "
              f"{r.provider[:40]:<40} {r.count:>3}")
    _pause()


def report_disadvantage_gap() -> None:
    print("\n═══ Disadvantage Gap ═══")
    tag = _input("Tag to compare against cohort",
                    default="Bursary recipient")
    year = _input("Leaving year (blank = all years)")
    try:
        rows = alumni_outcomes.disadvantage_gap(
            tag_name=tag,
            leaving_year=year or None)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  Tag: '{tag}'"
          + (f"  Year: {year}" if year else ""))
    print(f"\n  {'Destination':<16} "
          f"{'Cohort':>8} {'Coh %':>7} "
          f"{'Tagged':>8} {'Tag %':>7} {'Gap':>7}")
    print("  " + "-" * 60)
    for r in rows:
        print(f"  {r.destination_type:<16} "
              f"{r.cohort_count:>8} {r.cohort_pct:>6.1f}% "
              f"{r.tagged_count:>8} {r.tagged_pct:>6.1f}% "
              f"{r.gap_pct:>+6.1f}%")
    _pause()


def report_geographic() -> None:
    print("\n═══ Geographic Distribution ═══")
    rows = alumni_outcomes.geographic_distribution()
    if not rows:
        print("\n  (no location data)")
        _pause()
        return
    print(f"\n  {'Country':<24} {'Region':<24} {'#':>5}")
    print("  " + "-" * 60)
    for g in rows:
        print(f"  {g.country[:24]:<24} {g.region[:24]:<24} "
              f"{g.count:>5}")
    _pause()


def report_sector_breakdown() -> None:
    print("\n═══ Sector Breakdown ═══")
    rows = alumni_outcomes.sector_breakdown()
    print(f"\n  {'Sector':<24} {'#':>6} {'%':>7}")
    print("  " + "-" * 40)
    for r in rows:
        print(f"  {r.sector[:24]:<24} {r.count:>6} {r.pct:>6.1f}%")
    _pause()


def report_where_are_they_now() -> None:
    print("\n═══ Generate 'Where are they now' site ═══")
    print("  Only alumni with active 'Photo Use' consent are "
           "included.\n")
    try:
        out_dir = _input("Output directory", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        n = alumni_outcomes.generate_where_are_they_now(out_dir)
    except Exception as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Wrote {n} profile page(s) + index.html to {out_dir}")
    _pause()


# ── Operational quality ──────────────────────────────────────────

def import_csv_flow() -> None:
    print("\n═══ Bulk CSV Import ═══")
    try:
        path = _input("CSV file path", allow_empty=False)
        rows = alumni_bulk_io.parse_import_csv(path)
        print(f"\n  Parsed {len(rows)} row(s).")
        if not rows:
            _pause(); return
        suggestion = alumni_bulk_io.suggest_import_mapping(
            list(rows[0].keys()))
        print("\n  Suggested column mapping:")
        for csv_col, field in suggestion.items():
            print(f"    {csv_col!r:<28} → {field}")
        unknown = [c for c in rows[0] if c not in suggestion]
        if unknown:
            print(f"\n  Unmapped columns: "
                   f"{', '.join(repr(c) for c in unknown)}")
            if _yes_no("Map any of them now?", default=False):
                for col in unknown:
                    target = _input(
                        f"Map {col!r} to (blank to skip)")
                    if target:
                        suggestion[col] = target
        preview = alumni_bulk_io.preview_import(rows, suggestion)
        print("\n  Dry-run:")
        print(f"    create  : {preview.will_create}")
        print(f"    update  : {preview.will_update}")
        print(f"    skip    : {preview.will_skip}")
        if preview.errors:
            print("\n  First few problems:")
            for ln, msg in preview.errors[:10]:
                print(f"    row {ln}: {msg}")
        if not _yes_no("Commit import?", default=False):
            print("\n  Cancelled.")
            _pause(); return
        actor = _input("Actor / staff id (optional)") or None
        result = alumni_bulk_io.apply_import(rows, suggestion, actor=actor)
        print(f"\n  ✓ created={result.created}  "
               f"updated={result.updated}  skipped={result.skipped}")
        if result.errors:
            print(f"    + {len(result.errors)} row error(s)")
    except _UserAbort:
        print("\n  Cancelled.")
    except (ValidationError, Exception) as e:
        print(f"  ✗ {e}")
    _pause()


def export_csv_flow() -> None:
    print("\n═══ Bulk CSV Export ═══")
    all_cols = [f for f, _ in alumni_models.EXPORT_FIELDS]
    print("  Available columns:")
    for i, c in enumerate(all_cols, 1):
        print(f"    {i:>2}) {c}")
    try:
        picks = _input(
            "Columns (comma-separated numbers, blank = all)")
        out = _input("Output path", allow_empty=False)
        respect = _yes_no(
            "Apply consent-based PII redaction?", default=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    cols: list[str] | None = None
    if picks.strip():
        try:
            idxs = [int(p) for p in picks.split(",") if p.strip()]
            cols = [all_cols[i - 1] for i in idxs]
        except (ValueError, IndexError):
            print("  ✗ Bad column selection."); _pause(); return
    try:
        path = alumni_bulk_io.export_alumni_csv(
            out_path=out, columns=cols, respect_consent=respect)
    except ValidationError as e:
        print(f"  ✗ {e}"); _pause(); return
    print(f"\n  ✓ Wrote {path}")
    _pause()


def dedupe_flow() -> None:
    print("\n═══ Duplicate Detection ═══")
    try:
        thresh = float(
            _input("Similarity threshold (0..1)", default="0.85"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled."); return
    dups = alumni_records.find_duplicates(threshold=thresh)
    print(f"\n  {len(dups)} candidate pair(s):")
    for i, d in enumerate(dups, 1):
        print(f"    {i:>2}) {d.score:.2f}  "
              f"#{d.primary.alumni_id} {d.primary.full_name} "
              f"(DOB {d.primary.dob or '—'}) "
              f"⇆ #{d.other.alumni_id} {d.other.full_name} "
              f"(DOB {d.other.dob or '—'})")
    if not dups:
        _pause(); return
    print("\n    m) Merge a pair    0) Back")
    try:
        choice = _input("Choice", default="0").lower()
        if choice == "m":
            n = int(_input("Pair #", allow_empty=False))
            if not (1 <= n <= len(dups)):
                print("  ✗ out of range"); _pause(); return
            d = dups[n - 1]
            print(f"  Will keep #{d.primary.alumni_id} "
                   f"({d.primary.full_name}), absorbing "
                   f"#{d.other.alumni_id}.")
            if not _yes_no("Proceed?", default=False):
                print("  Cancelled."); _pause(); return
            actor = _input("Actor / staff id (optional)") or None
            merged = alumni_records.merge_alumni(
                d.primary.alumni_id, d.other.alumni_id, actor=actor)
            print(f"\n  ✓ Merged into #{merged.alumni_id}")
    except _UserAbort:
        print("\n  Cancelled.")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def merge_flow() -> None:
    print("\n═══ Merge Alumni ═══")
    try:
        keep = int(_input("Keep alumnus #id (the survivor)",
                             allow_empty=False))
        other = int(_input("Merge alumnus #id (will be absorbed)",
                              allow_empty=False))
        if not _yes_no(
                f"Merge #{other} into #{keep}? Irreversible.",
                default=False):
            print("  Cancelled."); _pause(); return
        actor = _input("Actor / staff id (optional)") or None
        merged = alumni_records.merge_alumni(keep, other, actor=actor)
        print(f"\n  ✓ Merged. Result: #{merged.alumni_id} "
               f"{merged.full_name}")
    except _UserAbort:
        print("\n  Cancelled.")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def audit_log_flow() -> None:
    print("\n═══ Audit Log ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled."); return
    log = alumni_records.list_audit_log(a.alumni_id)
    if not log:
        print("\n  (no audited changes yet)")
        _pause(); return
    print(f"\n  {'When':<19}  {'Who':<14}  {'Field':<22}  Change")
    print("  " + "-" * 90)
    for r in log:
        old = (r['old_value'] or '—')[:18]
        new = (r['new_value'] or '—')[:18]
        print(f"  {r['changed_at']:<19}  {r['changed_by'][:14]:<14}  "
              f"{r['field'][:22]:<22}  {old} → {new}")
    _pause()


def trash_flow() -> None:
    print("\n═══ Soft-Delete Trash ═══")
    rows = alumni_records.list_soft_deleted()
    if not rows:
        print("\n  (trash is empty)")
        _pause(); return
    print(f"\n  {len(rows)} soft-deleted alumnus/alumni:")
    for r in rows:
        print(f"    #{r.alumni_id:<3} {r.full_name:<28} "
              f"deleted {r.deleted_at}")
    print("\n    r) Restore   p) Purge one   "
           "P) Purge all expired  0) Back")
    try:
        choice = _input("Choice", default="0").lower()
        if choice == "r":
            aid = int(_input("Alumni #id", allow_empty=False))
            alumni_records.restore_alumnus(aid)
            print("    ✓ Restored")
        elif choice == "p":
            aid = int(_input("Alumni #id", allow_empty=False))
            if _yes_no(f"Hard delete #{aid}? Irreversible.",
                         default=False):
                alumni_records.purge_alumnus(aid)
                print("    ✓ Purged")
        elif choice == "P":
            days = int(
                _input("Purge entries older than (days)",
                        default=str(alumni_models.SOFT_DELETE_UNDO_DAYS)))
            n = alumni_records.purge_expired_soft_deletes(undo_days=days)
            print(f"    ✓ Purged {n}")
    except _UserAbort:
        print("\n  Cancelled.")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def saved_searches_flow() -> None:
    print("\n═══ Saved Searches ═══")
    while True:
        rows = alumni_bulk_io.list_saved_searches()
        print(f"\n  {len(rows)} saved search(es):")
        for s in rows:
            owner = f" [{s.owner_staff_id}]" if s.owner_staff_id else ""
            print(f"    #{s.search_id:<3} {s.name:<28}{owner}  "
                   f"{s.filters}")
        print("\n    s) Save current filter  r) Run  "
               "d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "s":
                name = _input("Name", allow_empty=False)
                year = _input("Filter: leaving year") or None
                dest = _input(f"Filter: destination "
                                 f"({'/'.join(DESTINATION_TYPES)})"
                                 ) or None
                emp = _input("Filter: employer contains") or None
                uni = _input("Filter: university contains") or None
                sec = _input("Filter: sector "
                                f"(blank or {SECTORS[0]}…)") or None
                country = _input("Filter: country") or None
                tag = _input("Filter: tag") or None
                opt_in = (_yes_no("Contactable only?", default=False))
                filters: dict[str, Any] = {}
                if year:    filters["leaving_year"] = year
                if dest:    filters["destination_type"] = dest
                if emp:     filters["employer"] = emp
                if uni:     filters["university"] = uni
                if sec:     filters["sector"] = sec
                if country: filters["country"] = country
                if tag:     filters["tag"] = tag
                if opt_in:  filters["contactable_only"] = True
                replace = _yes_no("Replace if name exists?",
                                     default=False)
                staff = _input("Owner staff id (optional)") or None
                alumni_bulk_io.save_search(name, filters,
                                   owner_staff_id=staff,
                                   replace=replace)
                print("    ✓ Saved")
            elif choice == "r":
                name = _input("Saved-search name",
                                 allow_empty=False)
                results = alumni_bulk_io.run_saved_search(name)
                _print_alumni(results)
                _pause()
            elif choice == "d":
                name = _input("Saved-search name",
                                 allow_empty=False)
                if alumni_bulk_io.delete_saved_search(name):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def surveys_flow() -> None:
    print("\n═══ Surveys ═══")
    while True:
        rows = alumni_surveys.list_surveys()
        print(f"\n  {len(rows)} survey(s):")
        for s in rows:
            stats = alumni_surveys.survey_stats(s.survey_id)
            print(f"    #{s.survey_id:<3} [{s.status:<7}] "
                  f"{s.name[:30]:<30}  "
                  f"inv={stats.invited} sent={stats.sent} "
                  f"completed={stats.completed}")
        print("\n    a) Create  i) Invite cohort  v) View responses  "
               "c) Close  d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                name = _input("Survey name", allow_empty=False)
                desc = _input("Description")
                print("  Add questions one per line. Format:")
                print("    key | prompt | type")
                print(f"    types: {', '.join(sorted(alumni_surveys.SURVEY_QUESTION_TARGETS))}")
                print("  End with a blank line.")
                qs: list[dict[str, Any]] = []
                while True:
                    line = _input("Question",
                                     default="").strip()
                    if not line:
                        break
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) < 2:
                        print("    Need at least key | prompt"); continue
                    qkey = parts[0]
                    qprompt = parts[1]
                    qtype = parts[2] if len(parts) >= 3 else "freeform"
                    qs.append({"key": qkey, "prompt": qprompt,
                                 "type": qtype})
                if not qs:
                    print("  No questions — cancelled."); continue
                s = alumni_surveys.create_survey(name, qs,
                                          description=desc or None)
                print(f"    ✓ Created survey #{s.survey_id}")
            elif choice == "i":
                sid = int(_input("Survey #id", allow_empty=False))
                year = _input("Filter: leaving year") or None
                staff = _input("Sender staff id (optional)") or None
                filters: dict[str, Any] = {"status": "Active"}
                if year:
                    filters["leaving_year"] = year
                sent, skipped = alumni_surveys.send_survey_invitations(
                    sid, filters, staff_id=staff)
                print(f"    ✓ sent={sent}  skipped={skipped}")
            elif choice == "v":
                sid = int(_input("Survey #id", allow_empty=False))
                resps = alumni_surveys.list_survey_responses(sid)
                print(f"\n  {len(resps)} response(s):")
                for r in resps:
                    print(f"    resp #{r.response_id:<3} "
                          f"inv #{r.invitation_id:<3}  {r.submitted_at}")
                    for k, v in r.answers.items():
                        print(f"      {k}: {v}")
                _pause()
            elif choice == "c":
                sid = int(_input("Survey #id", allow_empty=False))
                alumni_surveys.close_survey(sid)
                print("    ✓ Closed")
            elif choice == "d":
                sid = int(_input("Survey #id", allow_empty=False))
                if _yes_no("Delete survey + invitations + "
                             "responses?", default=False):
                    alumni_surveys.delete_survey(sid)
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")
