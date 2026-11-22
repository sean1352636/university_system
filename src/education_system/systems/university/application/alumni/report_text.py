"""Plain-text rendering of the alumni office reports built by
:mod:`~education_system.systems.university.application.alumni.reports`.

Takes the report dicts only (no database access); a missing figure is
shown as "not recorded" / "None recorded" rather than a number.
"""

from __future__ import annotations

from datetime import datetime


def _day(value) -> str:
    return str(value or "")[:10]


def _pct(part, whole) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "-"


def _money(value) -> str:
    return f"£{float(value or 0):,.2f}"


def _rule(title, width=60):
    return [title, "=" * width]


def _range_line(r):
    if not (r.get("start") or r.get("end")):
        return "Period: all records"
    return f"Period: {r.get('start') or 'start'} to {r.get('end') or 'today'}"


def _list(lines, heading, pairs, total=None, empty="None recorded", fmt=str):
    if heading:
        lines.append(heading)
    if not pairs:
        lines.append(f"  {empty}")
    for key, value in pairs:
        share = f" ({_pct(value, total)})" if total else ""
        lines.append(f"  - {key}: {fmt(value)}{share}")
    lines.append("")


def _summary_lines(r, demographics=True, geographic=True):
    lines = []
    if not r["total"]:
        return ["No alumni records yet. Alumni appear here once graduates are registered "
                "(Alumni records > Add, or automatically at conferral).", ""]
    if demographics:
        lines += ["OVERALL", f"  Alumni records: {r['total']:,} ({r['living']:,} living, "
                  f"{r['deceased']} deceased, {r['erased']} erased)",
                  f"  Active in the last 6 months: {r['active_6m']:,} "
                  f"({_pct(r['active_6m'], r['living'])})",
                  f"  Registered this year: {r['new_this_year']:,}",
                  f"  Average graduation year: {r['avg_grad_year'] or 'not recorded'}",
                  f"  Marked as donors: {r['donors']:,}   Marked as mentors: {r['mentors']:,}", "",
                  "ENGAGEMENT POINTS",
                  f"  Total: {r['points_total']:,}   Average per alumnus: {r['points_avg']}"]
        if r["leaders"]:
            top = r["leaders"][0]
            lines.append(f"  Most engaged: {top['name']} ({top['points']:,} points)")
        else:
            lines.append("  No engagement points recorded yet")
        lines.append("")
        _list(lines, "BY GRADUATION DECADE", r["decades"], r["living"], "No graduation years recorded")
        _list(lines, "BY INDUSTRY", r["industries"], r["living"])
        c = r["consent"]
        lines += ["CONTACT", f"  Marketing consent: yes {c.get('yes', 0)}, no {c.get('no', 0)}, "
                  f"not asked {c.get('not asked', 0)}",
                  f"  Contactable (not suppressed): {r['contactable']:,}",
                  f"  E-mail bounced: {r['bounced']:,}", ""]
    if geographic:
        _list(lines, "BY COUNTRY", r["locations"]["countries"], r["living"])
        _list(lines, "TOP TOWNS AND CITIES", r["locations"]["cities"], r["living"],
              "No towns or cities recorded")
    return lines


def _engagement_lines(r):
    lines = [f"Alumni with recorded activity (points, posts, gifts, stories): "
             f"{r['participants']:,}",
             f"Recorded activities: {r['total_activities']:,}", ""]
    _list(lines, "ACTIVITY", [(k, v) for k, v in r["activity"].items()], r["total_activities"])
    lines.append(f"ENGAGEMENT POINTS ({r['points_source']}): {r['points_total']:,}")
    lines.append("")
    _list(lines, "POINTS BY ACTIVITY TYPE", r["point_kinds"], empty="No points ledger entries")
    lines.append("TOP ENGAGED ALUMNI")
    if not r["leaders"]:
        lines.append("  No engagement points recorded yet")
    for i, p in enumerate(r["leaders"], 1):
        acts = f" ({p['activities']} activities)" if p["activities"] else ""
        lines.append(f"  {i}. {p['name']}: {p['points']:,} points{acts}")
    lines.append("")
    _list(lines, "ACTIVITIES BY MONTH", r["monthly"], empty="No dated activity")
    lines += [f"NEWSLETTERS SENT: {r['newsletters_sent']} "
              f"({r['newsletter_recipients']:,} recipients)", ""]
    _list(lines, "BADGES EARNED", r["badges"], empty="No badges earned")
    return lines


def _giving_lines(r, full=True):
    if not r["gifts"] and not r["campaigns"]:
        return ["No gifts or campaigns recorded in this period.", ""]
    lines = ["OVERVIEW", f"  Received: {_money(r['total'])} from {r['gifts']:,} gifts "
             f"by {r['donors']:,} donors", f"  Average gift: {_money(r['average'])}",
             f"  Recurring / pledge gifts: {r['recurring']:,}",
             f"  Gift Aided gifts: {r['gift_aided']:,}",
             f"  Refunded: {r['refunded']} ({_money(r['refunded_total'])})",
             f"  Alumni participation: {r['participation']}"]
    if r["repeat"] is not None:
        lines.append(f"  Donors who also gave before the period: {r['repeat']:,}")
    lines += ["", "CAMPAIGNS"] + _campaign_lines(r["campaigns"]) + [""]
    if full:
        lines += _gift_size_lines(r)
    _list(lines, "PAYMENT METHODS", r["methods"], fmt=_money, empty="No gifts")
    return lines + _donor_lines(r)


def _campaign_lines(campaigns):
    if not campaigns:
        return ["  No campaigns"]
    lines = []
    for c in campaigns:
        goal = float(c.get("goal_amount") or 0)
        prog = f" of {_money(goal)} goal ({c['progress_pct']}%)" if goal else " (no goal set)"
        lines.append(f"  - {c.get('campaign_name')}: {_money(c.get('raised'))}{prog} "
                     f"[{c.get('status') or 'active'}]")
    return lines


def _gift_size_lines(r):
    lines = ["GIFT SIZES"]
    for label, n, amount in r["bands"]:
        lines.append(f"  {label}: {n} gifts ({_pct(n, r['gifts'])}) - {_money(amount)}")
    lines += ["", "BY MONTH"]
    if not r["monthly"]:
        lines.append("  No gifts")
    for month, amount, n in r["monthly"]:
        lines.append(f"  {month}: {_money(amount)} ({n} gifts)")
    lines.append("")
    return lines


def _donor_lines(r):
    lines = ["MAJOR GIFTS (£1,000 and over)"]
    if not r["major"]:
        lines.append("  None in this period")
    for i, g in enumerate(r["major"], 1):
        camp = f" ({g['campaign']})" if g["campaign"] else ""
        lines.append(f"  {i}. {g['name']}: {_money(g['amount'])}{camp} on {g['date']}")
    lines += ["", "DONOR RECOGNITION (lifetime giving)"]
    for name, n, amount in r["levels"]:
        lines.append(f"  {name}: {n} donors ({_money(amount)})")
    lines += ["", "PLEDGES AND GIFT AID",
              f"  Active pledges: {r['pledges_active']}   Overdue (14+ days): "
              f"{r['pledges_overdue']}"]
    if not r["claims"]:
        lines.append("  No Gift Aid claims yet")
    for c in r["claims"][:5]:
        lines.append(f"  Claim {c['claim_id']} {c.get('period_from')} to {c.get('period_to')}: "
                     f"{_money(c.get('claim_total'))} [{c.get('status')}]")
    lines.append("")
    return lines


def _events_lines(r):
    if not r["events"]:
        return ["No alumni events in this period.", ""]
    lines = ["OVERVIEW", f"  Events: {r['events']} ({r['past']} held, {r['upcoming']} upcoming, "
             f"{r['cancelled']} cancelled)", f"  Registrations: {r['registered']:,} "
             f"(waitlisted {r['waitlisted']})",
             f"  Attended (held events): {r['attended']:,} - attendance {r['attendance_rate']}",
             f"  Virtual / hybrid events: {r['virtual']}   Paid events: {r['paid']}",
             f"  Registration income: {_money(r['revenue'])}"]
    lines.append(f"  Average feedback: {r['rating']}/5 from {r['ratings']} ratings"
                 if r["rating"] is not None else "  No feedback ratings recorded")
    lines.append("")
    _list(lines, "BY TYPE", r["types"], r["events"])
    _list(lines, "BY MONTH", r["monthly"])
    lines.append("BEST ATTENDED (held events)")
    if not r["best"]:
        lines.append("  No registrations for held events")
    for i, e in enumerate(r["best"], 1):
        lines.append(f"  {i}. {e['title']} ({e['date']}): {e['attended']}/{e['registered']} "
                     f"({_pct(e['attended'], e['registered'])})")
    lines.append("")
    return lines


def _mentoring_lines(r):
    lines = [f"Matches: {r['matches']}  Mentors: {r['mentors']}  Mentees: {r['mentees']}"]
    if r["avg_days"] is not None:
        lines.append(f"Average length of ended matches: {r['avg_days']} days")
    lines += [f"Open concerns: {r['open_concerns']}", ""]
    _list(lines, "BY STATUS", r["status"], r["matches"], "No matches")
    _list(lines, "FOCUS AREAS", r["focus"], r["matches"], "No matches")
    _list(lines, "MENTOR VETTING", r["vetting"], empty="No mentor offers")
    return lines


def _usage_lines(r):
    n = r["alumni"]
    lines = ["ACTIVITY (from alumni last-activity dates)",
             f"  Living alumni: {n:,}", f"  Active today: {r['active_1']} ({_pct(r['active_1'], n)})",
             f"  Active in 7 days: {r['active_7']} ({_pct(r['active_7'], n)})",
             f"  Active in 30 days: {r['active_30']} ({_pct(r['active_30'], n)})",
             f"  Active in 90 days: {r['active_90']} ({_pct(r['active_90'], n)})",
             f"  No activity recorded: {r['never_active']}", ""]
    _list(lines, "FEATURE TAKE-UP (people)", [(k, v if v is not None else 0)
                                              for k, v in r["adoption"].items()])
    _list(lines, "CONTENT", [(k, v if v is not None else 0) for k, v in r["content"].items()])
    lines += [f"OFFICE ACTIVITY, LAST 30 DAYS (alumni audit trail): {r['audit_30']} actions by "
              f"{r['audit_actors']} people"]
    _list(lines, "", r["audit_actions"], empty="No recorded actions")
    lines.append("NEWSLETTERS")
    if not r["newsletters"]:
        lines.append("  None created")
    for nl in r["newsletters"][:10]:
        sent = (f"sent {_day(nl['sent_at'])} to {nl.get('sent_count') or 0} "
                f"({nl.get('suppressed_count') or 0} suppressed)" if nl.get("sent_at")
                else nl.get("status") or "draft")
        lines.append(f"  - {nl.get('title')}: {sent}")
    lines += ["", "Page views, sessions, devices and browsers are not recorded by this system."]
    return lines


TITLES = {"summary": "ALUMNI SUMMARY REPORT", "engagement": "ALUMNI ENGAGEMENT REPORT",
          "giving": "DONATION ANALYSIS REPORT", "events": "EVENT ATTENDANCE REPORT",
          "mentoring": "MENTORING REPORT", "usage": "SYSTEM USAGE ANALYTICS",
          "custom": "CUSTOM ALUMNI REPORT", "recognition": "DONOR RECOGNITION LEVEL REPORT"}


_SECTION_HEADS = {"demographics": "ALUMNI DEMOGRAPHICS", "engagement": "ENGAGEMENT METRICS",
                  "events": "EVENT STATISTICS", "donations": "DONATION ANALYSIS",
                  "mentorships": "MENTORSHIP DATA", "geographic": "GEOGRAPHIC DISTRIBUTION"}
_SECTION_LINES = {
    "demographics": lambda p: _summary_lines(p["summary"], geographic=False),
    "geographic": lambda p: _summary_lines(p["summary"], demographics=False),
    "engagement": lambda p: _engagement_lines(p["engagement"]),
    "events": lambda p: _events_lines(p["events"]),
    "donations": lambda p: _giving_lines(p["giving"], full=False),
    "mentorships": lambda p: _mentoring_lines(p["mentoring"]),
}


def _custom_lines(report):
    lines = []
    for s in report["sections"]:
        lines += ["", _SECTION_HEADS[s], "-" * 40] + _SECTION_LINES[s](report["parts"])
    return lines


def render(report: dict, giving_full=True) -> str:
    kind = report["kind"]
    lines = _rule(TITLES[kind]) + [f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}"]
    if kind != "usage":
        lines.append(_range_line(report))
    lines.append("")
    body = {"summary": _summary_lines, "engagement": _engagement_lines,
            "giving": lambda r: _giving_lines(r, giving_full), "events": _events_lines,
            "mentoring": _mentoring_lines, "usage": _usage_lines, "custom": _custom_lines}
    lines += body[kind](report)
    return "\n".join(lines).rstrip() + "\n"


def render_recognition(report: dict) -> str:
    """Just the recognition levels from a :func:`giving_report`."""
    lines = _rule(TITLES["recognition"], 40) + [f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
                                                "Lifetime giving per alumnus", ""]
    total_n = total_amount = 0
    for name, n, amount in report["levels"]:
        lines.append(f"{name}: {n} donor{'s' if n != 1 else ''} ({_money(amount)})")
        total_n += n
        total_amount += amount
    lines += ["-" * 40, f"Total: {total_n} donors ({_money(total_amount)})"]
    if not total_n:
        lines.append("No gifts from alumni recorded yet.")
    return "\n".join(lines) + "\n"
