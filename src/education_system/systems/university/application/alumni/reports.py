"""Alumni office reports, worked out from the alumni records, gifts,
mentoring, events and community tables (nothing is estimated).

Each ``*_report`` function returns a dict of figures; :func:`render`
(from ``report_text``, re-exported here) turns one into the plain text the reports window shows, saves and e-mails. Where
the data is not there, the report says so instead of showing a number.

* Gifts, campaigns, pledges and Gift Aid claims come from ``giving``;
  alumni from ``records.listing``; matches and mentor vetting from
  ``community``; newsletters from ``comms``.
* A date range (``start``/``end``, ISO dates, either may be blank) limits
  the dated figures: gifts, registrations, events, points, posts, matches.
  Head counts (alumni, demographics) are as of today.

Office only. Functions take an open connection and do not commit.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from education_system.systems.university.application.alumni import access as aa
from education_system.systems.university.application.alumni import comms, community, giving
from education_system.systems.university.application.alumni import records
from education_system.systems.university.application.alumni.report_text import (  # noqa: F401
    TITLES,
    _pct,
    render,
    render_recognition,
)

RANGES = ((0, 50), (50, 100), (100, 500), (500, 1000), (1000, 5000), (5000, None))
CUSTOM_SECTIONS = ("demographics", "engagement", "events", "donations", "mentorships",
                   "geographic")
_ATTENDED = ("attended", "checked_in", "present")
_COUNTED = frozenset({"alumni_directory_settings", "chapter_memberships", "alumni_forum",
                      "forum_replies", "alumni_stories", "photo_gallery",
                      "alumni_content_reports"})


def _require(who):
    aa.require(who is not None and who.is_office, "Only the alumni office can run alumni reports")


def _day(value) -> str:
    return str(value or "")[:10]


def _in(value, start, end) -> bool:
    day = _day(value)
    if not day:
        return not (start or end)
    return (not start or day >= start) and (not end or day <= end)


def _period(start, end):
    return (aa.iso_date(start, "From") or "", aa.iso_date(end, "To") or "")


def _count(conn, table, where="", params=()) -> int | None:
    """Row count, or None when the table does not exist here."""
    if table not in _COUNTED:
        raise ValueError(f"Not a reportable table: {table}")
    if not aa.has_table(conn, table):
        return None
    # db-audit: ignore[DBW001] - table is from the _COUNTED allow-list, where is a literal
    sql = f"SELECT COUNT(*) FROM {table}" + (f" WHERE {where}" if where else "")
    return int(conn.execute(sql, params).fetchone()[0])


def _top(counter: Counter, n=8):
    return [(k, v) for k, v in counter.most_common(n)]


def _name(row) -> str:
    return " ".join(p for p in (row.get("first_name"), row.get("last_name")) if p) \
        or str(row.get("alumni_id"))


def _living(rows):
    return [r for r in rows if not r.get("anonymised_at") and not r.get("deceased_at")]


# ── points ──────────────────────────────────────────────────────────────


def _points(conn, start, end) -> dict:
    """Engagement points per alumnus from the ``engagement_points`` ledger,
    falling back to ``alumni.engagement_score`` when the ledger is empty."""
    per, kinds, activities = Counter(), Counter(), Counter()
    if aa.has_table(conn, "engagement_points"):
        for r in aa.dicts(conn.execute("SELECT alumni_id, activity_type, points_earned, "
                                       "activity_date FROM engagement_points")):
            if _in(r["activity_date"], start, end):
                per[r["alumni_id"]] += int(r["points_earned"] or 0)
                kinds[r["activity_type"] or "other"] += 1
                activities[r["alumni_id"]] += 1
    source = "engagement_points"
    if not per:
        source = "alumni.engagement_score"
        for aid, score in conn.execute("SELECT alumni_id, engagement_score FROM alumni WHERE "
                                       "COALESCE(engagement_score, 0) > 0"):
            per[aid] = int(score)
    return {"per": per, "kinds": kinds, "activities": activities, "source": source}


def _leaders(conn, points, n=5):
    names = {r["alumni_id"]: _name(r) for r in aa.dicts(conn.execute(
        "SELECT alumni_id, first_name, last_name FROM alumni WHERE anonymised_at IS NULL"))}
    return [{"name": names[aid], "points": pts, "activities": points["activities"].get(aid, 0)}
            for aid, pts in points["per"].most_common() if aid in names][:n]


# ── summary ─────────────────────────────────────────────────────────────


def summary_report(conn, who, start=None, end=None) -> dict:
    _require(who)
    start, end = _period(start, end)
    everyone = records.listing(conn, who)
    alive = _living(everyone)
    points = _points(conn, start, end)
    total_points = sum(points["per"].values())
    report = {
        "kind": "summary", "start": start, "end": end,
        "points_total": total_points, "points_source": points["source"],
        "points_avg": round(total_points / len(alive), 1) if alive else 0,
        "leaders": _leaders(conn, points, 1),
    }
    report.update(_head_counts(everyone, alive))
    report.update(_demographics(alive))
    return report


def _head_counts(everyone, alive) -> dict:
    six_months = (date.today() - timedelta(days=183)).isoformat()
    this_year = f"{date.today().year}-01-01"
    return {
        "total": len(everyone), "living": len(alive),
        "deceased": sum(1 for r in everyone if r.get("deceased_at")),
        "erased": sum(1 for r in everyone if r.get("anonymised_at")),
        "active_6m": sum(1 for r in alive if _day(r.get("last_activity")) >= six_months),
        "new_this_year": sum(1 for r in alive if _day(r.get("date_registered")) >= this_year),
        "contactable": sum(1 for r in alive if aa.contactable(r)),
        "bounced": sum(1 for r in alive if r.get("email_bounced")),
        "mentors": sum(1 for r in alive if r.get("is_mentor")),
        "donors": sum(1 for r in alive if r.get("is_donor")),
    }


def _consent_word(row) -> str:
    value = row.get("marketing_consent")
    return "yes" if value == 1 else "no" if value == 0 else "not asked"


def _demographics(alive) -> dict:
    years = [int(r["graduation_year"]) for r in alive
             if str(r.get("graduation_year") or "").strip().isdigit()]
    decades = Counter(f"{y // 10 * 10}s" for y in years)
    return {
        "avg_grad_year": round(sum(years) / len(years)) if years else None,
        "decades": sorted(decades.items(), reverse=True),
        "industries": _top(Counter((r.get("industry") or "Not recorded").strip()
                                   for r in alive)),
        "locations": _locations(alive),
        "consent": dict(Counter(_consent_word(r) for r in alive)),
    }


def _locations(alive):
    countries = Counter((r.get("country") or "Not recorded").strip() for r in alive)
    cities = Counter(", ".join(p for p in ((r.get("city") or "").strip(),
                                           (r.get("country") or "").strip()) if p)
                     for r in alive if (r.get("city") or "").strip())
    return {"countries": _top(countries), "cities": _top(cities)}


# ── engagement ──────────────────────────────────────────────────────────


def _forum_replies(conn, start, end) -> int:
    if not aa.has_table(conn, "forum_replies"):
        return 0
    return sum(1 for (d,) in conn.execute("SELECT COALESCE(reply_date, created_date) FROM "
                                          "forum_replies WHERE hidden_at IS NULL")
               if _in(d, start, end))


def _connections(conn, start, end) -> Counter:
    connections = Counter()
    if aa.has_table(conn, "alumni_connections"):
        for status, day in conn.execute("SELECT status, request_date FROM alumni_connections"):
            if _in(day, start, end):
                connections[status or "pending"] += 1
    return connections


def _badges(conn, start, end) -> Counter:
    badges = Counter()
    if aa.has_table(conn, "alumni_badges") and aa.has_table(conn, "achievement_badges"):
        for name, day in conn.execute("SELECT b.badge_name, ab.earned_date FROM alumni_badges ab "
                                      "JOIN achievement_badges b ON b.badge_id = ab.badge_id"):
            if _in(day, start, end):
                badges[name] += 1
    return badges


def _dated(rows, field, start, end) -> list[dict]:
    return [r for r in rows if _in(r.get(field), start, end)]


def _engagement_rows(conn, who, start, end) -> dict:
    return {
        "posts": _dated(community.forum_posts(conn, who), "post_date", start, end),
        "stories": _dated(community.stories(conn, who), "publish_date", start, end),
        "photos": _dated(community.photos(conn, who), "upload_date", start, end),
        "gifts": [g for g in _dated(giving.gifts(conn, who), "donation_date", start, end)
                  if _received(g)],
        "matches": _dated(community.mentorships(conn, who), "start_date", start, end),
        "sent": [n for n in comms.newsletters(conn)
                 if n.get("sent_at") and _in(n["sent_at"], start, end)],
    }


def engagement_report(conn, who, start=None, end=None) -> dict:
    _require(who)
    start, end = _period(start, end)
    points = _points(conn, start, end)
    regs = _registrations(conn, start, end)
    got = _engagement_rows(conn, who, start, end)
    connections = _connections(conn, start, end)
    # Alumni ids only (event registrations key on the login, so they are counted separately).
    participants = set(points["activities"]) | {p.get("author_id") for p in got["posts"]} | \
        {g.get("alumni_id") for g in got["gifts"]} | {s.get("alumni_id") for s in got["stories"]}
    participants.discard(None)
    activity = {
        "Event registrations": len(regs),
        "Event check-ins": sum(1 for r in regs if r["attended"]),
        "Forum posts": len(got["posts"]), "Forum replies": _forum_replies(conn, start, end),
        "Connection requests": sum(connections.values()),
        "Connections accepted": connections.get("accepted", 0),
        "Stories published": len(got["stories"]), "Photos shared": len(got["photos"]),
        "Gifts": len(got["gifts"]), "Mentoring matches started": len(got["matches"]),
    }
    return {"kind": "engagement", "start": start, "end": end,
            "participants": len(participants), "activity": activity,
            "total_activities": sum(activity.values()),
            "points_total": sum(points["per"].values()), "points_source": points["source"],
            "point_kinds": _top(points["kinds"], 12), "leaders": _leaders(conn, points, 10),
            "newsletters_sent": len(got["sent"]),
            "newsletter_recipients": sum(int(n.get("sent_count") or 0) for n in got["sent"]),
            "badges": _top(_badges(conn, start, end), 12),
            "monthly": _monthly_points(conn, start, end)}


def _monthly_points(conn, start, end):
    months = Counter()
    if aa.has_table(conn, "engagement_points"):
        for (day,) in conn.execute("SELECT activity_date FROM engagement_points"):
            if day and _in(day, start, end):
                months[_day(day)[:7]] += 1
    return sorted(months.items())


# ── giving ──────────────────────────────────────────────────────────────


def _received(g) -> bool:
    return (g.get("status") or "received") == "received"


def _amount(g) -> float:
    return float(g["amount"] or 0)


def _gift_bands(got) -> list:
    bands = []
    for low, high in RANGES:
        hit = [_amount(g) for g in got
               if _amount(g) >= low and (high is None or _amount(g) < high)]
        label = f"£{low:,}+" if high is None else f"£{low:,} - £{high:,}"
        bands.append((label, len(hit), sum(hit)))
    return bands


def _gift_months(got) -> dict:
    months, month_n, methods = Counter(), Counter(), Counter()
    for g in got:
        month = _day(g.get("donation_date"))[:7] or "undated"
        months[month] += _amount(g)
        month_n[month] += 1
        methods[g.get("payment_method") or "not recorded"] += _amount(g)
    return {"monthly": sorted((m, months[m], month_n[m]) for m in months),
            "methods": sorted(methods.items(), key=lambda kv: -kv[1])}


def _recognition_levels(all_gifts) -> list:
    per_donor = Counter()
    for g in all_gifts:
        if _received(g) and g.get("alumni_id"):
            per_donor[g["alumni_id"]] += _amount(g)
    levels, level_totals = Counter(), Counter()
    for amount in per_donor.values():
        name = giving.recognition_level(amount) or "None"
        levels[name] += 1
        level_totals[name] += amount
    return [(name, levels.get(name, 0), round(level_totals.get(name, 0), 2))
            for _, name in giving.RECOGNITION]


def _donor_label(g, alumni_names) -> str:
    if (g.get("donor_name") or "").lower() == "anonymous":
        return "Anonymous"
    return alumni_names.get(g.get("alumni_id")) or g.get("donor_name") or "Unknown"


def _major_gifts(conn, got) -> list[dict]:
    alumni_names = {r["alumni_id"]: _name(r) for r in aa.dicts(conn.execute(
        "SELECT alumni_id, first_name, last_name, anonymised_at FROM alumni"))}
    major = sorted((g for g in got if _amount(g) >= 1000), key=lambda g: -_amount(g))[:10]
    return [{"name": _donor_label(g, alumni_names), "amount": float(g["amount"]),
             "campaign": g.get("campaign_name") or "", "date": _day(g.get("donation_date"))}
            for g in major]


def _gift_counts(got, refunded, alive) -> dict:
    total = sum(_amount(g) for g in got)
    return {
        "total": round(total, 2), "gifts": len(got),
        "donors": len({g.get("alumni_id") or f"name:{g.get('donor_name')}" for g in got}),
        "average": round(total / len(got), 2) if got else 0,
        "recurring": sum(1 for g in got if g.get("is_recurring") or g.get("pledge_id")),
        "refunded": len(refunded),
        "refunded_total": round(sum(_amount(g) for g in refunded), 2),
        "gift_aided": sum(1 for g in got if g.get("gift_aid_declaration_id")
                          or g.get("is_gift_aided")),
        "participation": _pct(len({g.get("alumni_id") for g in got if g.get("alumni_id")}),
                              len(alive)),
    }


def _repeat_donors(all_gifts, got, start):
    if not start:
        return None
    earlier = {g.get("alumni_id") for g in all_gifts if _received(g) and g.get("alumni_id")
               and _day(g.get("donation_date")) < start}
    return len({g.get("alumni_id") for g in got} & earlier)


def giving_report(conn, who, start=None, end=None) -> dict:
    _require(who)
    start, end = _period(start, end)
    all_gifts = giving.gifts(conn, who)
    period = _dated(all_gifts, "donation_date", start, end)
    got = [g for g in period if _received(g)]
    refunded = [g for g in period if (g.get("status") or "") == "refunded"]
    pledges = giving.pledges(conn, who)
    report = {"kind": "giving", "start": start, "end": end,
              "repeat": _repeat_donors(all_gifts, got, start), "bands": _gift_bands(got),
              "campaigns": giving.campaigns(conn), "major": _major_gifts(conn, got),
              "levels": _recognition_levels(all_gifts),
              "pledges_active": sum(1 for p in pledges if p.get("status") == "active"),
              "pledges_overdue": len(giving.overdue_pledges(conn)),
              "claims": giving.claims(conn)}
    report.update(_gift_counts(got, refunded, _living(records.listing(conn, who))))
    report.update(_gift_months(got))
    return report


# ── events ──────────────────────────────────────────────────────────────


def _registrations(conn, start, end) -> list[dict]:
    if not aa.has_table(conn, "unified_event_registrations"):
        return []
    rows = aa.dicts(conn.execute(
        "SELECT r.user_id, r.attendance_status, r.checked_in_at, r.check_in_time, "
        "r.is_waitlisted, COALESCE(r.registration_date, r.registered_at, r.created_at) AS day, "
        "r.feedback_rating, r.payment_amount, r.event_id FROM unified_event_registrations r "
        "JOIN unified_events e ON e.event_id = r.event_id WHERE e.source_type = 'alumni'"))
    out = []
    for r in rows:
        if _in(r["day"], start, end):
            r["attended"] = bool(r.get("checked_in_at") or r.get("check_in_time") or
                                 (r.get("attendance_status") or "").lower() in _ATTENDED)
            out.append(r)
    return out


def _alumni_events(conn, start, end) -> list[dict]:
    return [e for e in aa.dicts(conn.execute(
        "SELECT event_id, title, start_datetime, event_type, event_category, max_capacity, "
        "event_fee, status, virtual_link, location FROM unified_events WHERE source_type = "
        "'alumni' ORDER BY start_datetime")) if _in(e["start_datetime"], start, end)]


def _empty_tally() -> dict:
    return {"registered": 0, "attended": 0, "ratings": []}


def _tally_by_event(regs) -> dict:
    by_event = {}
    for r in regs:
        slot = by_event.setdefault(r["event_id"], _empty_tally())
        slot["registered"] += 1
        slot["attended"] += 1 if r["attended"] else 0
        if r.get("feedback_rating"):
            slot["ratings"].append(float(r["feedback_rating"]))
    return by_event


def _held(past, by_event) -> dict:
    rows = []
    for e in past:
        s = by_event.get(e["event_id"], _empty_tally())
        rows.append({"title": e["title"] or f"Event {e['event_id']}",
                     "date": _day(e["start_datetime"]), "registered": s["registered"],
                     "attended": s["attended"], "capacity": e.get("max_capacity")})
    attended = sum(r["attended"] for r in rows)
    return {"attended": attended,
            "attendance_rate": _pct(attended, sum(r["registered"] for r in rows)),
            "best": sorted((r for r in rows if r["registered"]),
                           key=lambda r: -(r["attended"] / r["registered"]))[:5]}


def _event_mix(events) -> dict:
    return {
        "cancelled": sum(1 for e in events if (e.get("status") or "").lower() == "cancelled"),
        "types": _top(Counter(e.get("event_type") or e.get("event_category") or "Not set"
                              for e in events)),
        "virtual": sum(1 for e in events if e.get("virtual_link")),
        "paid": sum(1 for e in events if float(e.get("event_fee") or 0) > 0),
        "monthly": sorted(Counter(_day(e["start_datetime"])[:7] for e in events).items()),
    }


def events_report(conn, who, start=None, end=None) -> dict:
    _require(who)
    start, end = _period(start, end)
    events = _alumni_events(conn, start, end)
    ids = {e["event_id"] for e in events}
    regs = [r for r in _registrations(conn, "", "") if r["event_id"] in ids]
    by_event = _tally_by_event(regs)
    today = date.today().isoformat()
    past = [e for e in events if _day(e["start_datetime"]) < today]
    ratings = [x for s in by_event.values() for x in s["ratings"]]
    report = {
        "kind": "events", "start": start, "end": end,
        "events": len(events), "past": len(past), "upcoming": len(events) - len(past),
        "registered": sum(s["registered"] for s in by_event.values()),
        "waitlisted": sum(1 for r in regs if r.get("is_waitlisted")),
        "revenue": round(sum(float(r.get("payment_amount") or 0) for r in regs), 2),
        "rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "ratings": len(ratings),
    }
    report.update(_held(past, by_event))
    report.update(_event_mix(events))
    return report


# ── mentoring ───────────────────────────────────────────────────────────


def mentoring_report(conn, who, start=None, end=None) -> dict:
    _require(who)
    start, end = _period(start, end)
    matches = [m for m in community.mentorships(conn, who) if _in(m.get("start_date"), start, end)]
    vetting = community.vetting_queue(conn, who)
    status = Counter(m.get("status") or "unknown" for m in matches)
    lengths = []
    for m in matches:
        if m.get("start_date") and m.get("end_date"):
            try:
                lengths.append((date.fromisoformat(_day(m["end_date"])) -
                                date.fromisoformat(_day(m["start_date"]))).days)
            except ValueError:
                pass
    return {"kind": "mentoring", "start": start, "end": end, "matches": len(matches),
            "status": sorted(status.items()),
            "mentors": len({m.get("mentor_id") for m in matches if m.get("mentor_id")}),
            "mentees": len({m.get("mentee_id") for m in matches if m.get("mentee_id")}),
            "focus": _top(Counter(m.get("focus_area") or "Not set" for m in matches)),
            "avg_days": round(sum(lengths) / len(lengths)) if lengths else None,
            "open_concerns": sum(int(m.get("open_concerns") or 0) for m in matches),
            "vetting": sorted(Counter(v.get("status") or "unknown" for v in vetting).items())}


# ── system analytics ────────────────────────────────────────────────────


def usage_report(conn, who) -> dict:
    """What the system records about use: activity dates, opt-ins, feature
    take-up and the alumni audit trail. Page views, devices and browsers
    are not recorded, so they are not reported."""
    _require(who)
    alive = _living(records.listing(conn, who))
    n = len(alive)
    today = date.today()

    def since(days):
        cut = (today - timedelta(days=days)).isoformat()
        return sum(1 for r in alive if _day(r.get("last_activity")) >= cut)

    audit = aa.recent_audit(conn, who, limit=5000)
    month_ago = (datetime.now() - timedelta(days=30)).isoformat(sep=" ")
    recent = [a for a in audit if str(a.get("at") or "") >= month_ago]
    regs = _registrations(conn, "", "")
    adoption = {
        "Listed in the directory": _count(conn, "alumni_directory_settings", "searchable = 1"),
        "Registered for an event": len({r["user_id"] for r in regs}),
        "Posted in the forum": len({p.get("author_id") for p in community.forum_posts(conn, who)}),
        "Mentors (vetted)": sum(1 for v in community.vetting_queue(conn, who)
                                if v.get("status") == "approved"),
        "Chapter members": _count(conn, "chapter_memberships"),
        "Donors": len({g.get("alumni_id") for g in giving.gifts(conn, who)
                       if _received(g) and g.get("alumni_id")}),
    }
    return {"kind": "usage", "alumni": n, "active_1": since(1), "active_7": since(7),
            "active_30": since(30), "active_90": since(90),
            "never_active": sum(1 for r in alive if not r.get("last_activity")),
            "adoption": adoption,
            "audit_30": len(recent),
            "audit_actions": _top(Counter(f"{a.get('entity')} {a.get('action')}"
                                          for a in recent), 12),
            "audit_actors": len({a.get("actor") for a in recent if a.get("actor")}),
            "newsletters": comms.newsletters(conn),
            "content": {"Forum posts": _count(conn, "alumni_forum"),
                        "Forum replies": _count(conn, "forum_replies"),
                        "Stories": _count(conn, "alumni_stories"),
                        "Photos": _count(conn, "photo_gallery"),
                        "Open content reports": _count(conn, "alumni_content_reports",
                                                       "status = 'open'")}}


def custom_report(conn, who, sections, start=None, end=None) -> dict:
    _require(who)
    unknown = [s for s in sections if s not in CUSTOM_SECTIONS]
    if unknown:
        raise ValueError(f"Unknown report section: {', '.join(unknown)}")
    if not sections:
        raise ValueError("Pick at least one section")
    parts = {}
    if "demographics" in sections or "geographic" in sections:
        parts["summary"] = summary_report(conn, who, start, end)
    if "engagement" in sections:
        parts["engagement"] = engagement_report(conn, who, start, end)
    if "events" in sections:
        parts["events"] = events_report(conn, who, start, end)
    if "donations" in sections:
        parts["giving"] = giving_report(conn, who, start, end)
    if "mentorships" in sections:
        parts["mentoring"] = mentoring_report(conn, who, start, end)
    start, end = _period(start, end)
    return {"kind": "custom", "start": start, "end": end, "sections": list(sections),
            "parts": parts}
