"""Graduation ceremonies: who belongs at one, invitations and reminders,
RSVPs with named guest tickets and extra-ticket requests, checking
graduands in on the day, no-shows and transfers, completing the ceremony
(which confers the award on everyone who attended) and gown refunds.

* A ceremony's **cohorts** (programme / department / award year) decide
  who it is for; with none set it is open to every eligible graduand.
* An RSVP needs an eligible graduand who was invited or is in the cohort,
  before the RSVP deadline, at a scheduled ceremony, within the guest
  allowance (plus any extra tickets granted) and the venue's capacity. The
  graduation office can override the deadline and the cohort.
* Accessibility needs are recorded as structured needs and copied into the
  RSVP's accessibility notes, which the seat plan seats first.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import secrets
from datetime import date, timedelta

from education_system.systems.university.application.graduation import access as ga
from education_system.systems.university.application.graduation import conferral as gc
from education_system.systems.university.application.graduation import eligibility as ge
from education_system.systems.university.domains.progression.domain.degree_audit import (
    graduation_ceremony as gcm,
)

COHORT_KINDS = ("programme", "department", "award_year")
RSVP_STATUSES = ("going", "not_going", "interested", "pending")
ACCESS_NEEDS = ("wheelchair", "step_free", "hearing_loop", "near_exit", "assistance_animal",
                "seated_crossing", "other")
REMIND_DAYS = 7


def ceremony(conn, ceremony_id) -> dict:
    ga.ensure(conn)
    row = ga.one(conn, "SELECT * FROM graduation_ceremonies WHERE ceremony_id = ?",
                 (ceremony_id,))
    if not row:
        raise ValueError("No such ceremony")
    return row


def _scheduled(row) -> None:
    if (row.get("status") or "scheduled") != "scheduled":
        raise ValueError(f"That ceremony is {row['status']}")


# ── cohorts ─────────────────────────────────────────────────────────────


def cohorts(conn, ceremony_id) -> list[dict]:
    ga.ensure(conn)
    return ga.dicts(conn.execute("SELECT kind, value FROM ceremony_cohorts WHERE ceremony_id = ? "
                                 "ORDER BY kind, value", (ceremony_id,)))


def set_cohorts(conn, who, ceremony_id, items) -> None:
    ga.require_office(who)
    ceremony(conn, ceremony_id)
    clean = []
    for kind, value in items:
        if kind not in COHORT_KINDS:
            raise ValueError("Cohort must be programme, department or award_year")
        clean.append((kind, ga.text(value, "Cohort value", True)))
    conn.execute("DELETE FROM ceremony_cohorts WHERE ceremony_id = ?", (ceremony_id,))
    conn.executemany("INSERT OR IGNORE INTO ceremony_cohorts VALUES (?, ?, ?)",
                     [(ceremony_id, k, v) for k, v in clean])
    conn.execute("UPDATE graduation_ceremonies SET cohort_filter = ? WHERE ceremony_id = ?",
                 ("; ".join(f"{k}={v}" for k, v in clean), ceremony_id))
    ga.audit(conn, who, "ceremony", ceremony_id, "cohorts", {"cohorts": clean})


def _department(conn, course) -> str:
    if not course or not ga.has_table(conn, "courses"):
        return ""
    row = conn.execute("SELECT department FROM courses WHERE course_code = ? OR code = ? LIMIT 1",
                       (course, course)).fetchone()
    return (row[0] or "") if row else ""


def in_cohort(conn, ceremony_id, student_id, award=None) -> bool:
    rules = cohorts(conn, ceremony_id)
    if not rules:
        return True
    st = ga.student(conn, student_id)
    award = award or ge.award(conn, student_id) or {}
    facts = {"programme": {str(st.get("course") or "").lower(),
                           str(award.get("programme_code") or "").lower()},
             "department": {_department(conn, st.get("course")).lower()},
             "award_year": {str(award.get("academic_year") or "").lower()}}
    return any(r["value"].lower() in facts[r["kind"]] or
               (r["kind"] == "award_year" and any(f.startswith(r["value"].lower())
                                                  for f in facts["award_year"] if f))
               for r in rules)


# ── graduands and invitations ───────────────────────────────────────────


def graduands(conn, who, ceremony_id) -> list[dict]:
    """Students with a released award, not yet conferred, in the cohort."""
    ga.require_office(who)
    ceremony(conn, ceremony_id)
    if not ga.has_table(conn, "ratified_student_awards"):
        return []
    ids = [r[0] for r in conn.execute(
        "SELECT DISTINCT student_id FROM ratified_student_awards WHERE status = 'ratified' AND "
        "release_authorised = 1 ORDER BY student_id")]
    invited = {r[0] for r in conn.execute("SELECT student_id FROM ceremony_invitations WHERE "
                                          "ceremony_id = ?", (ceremony_id,))}
    rsvp = dict(conn.execute("SELECT student_id, rsvp_status FROM ceremony_rsvps WHERE "
                             "ceremony_id = ?", (ceremony_id,)).fetchall())
    out = []
    for sid in ids:
        report = ge.check(conn, sid)
        if report["conferral"] or not in_cohort(conn, ceremony_id, sid, report["award"]):
            continue
        out.append({"student_id": sid, "name": report["student_name"],
                    "award": report["award"]["award_name"] if report["award"] else None,
                    "eligible": report["eligible"], "blockers": report["blockers"],
                    "name_confirmed": report["name_confirmed"], "invited": sid in invited,
                    "rsvp": rsvp.get(sid)})
    return out


def invite(conn, who, ceremony_id, student_ids=None) -> dict:
    """Invite the given (or every not-yet-invited eligible) graduand."""
    ga.require_office(who)
    row = ceremony(conn, ceremony_id)
    _scheduled(row)
    pool = {g["student_id"]: g for g in graduands(conn, who, ceremony_id)}
    targets = list(student_ids) if student_ids else [
        s for s, g in pool.items() if g["eligible"] and not g["invited"]]
    invited, skipped, emails = [], [], []
    for sid in targets:
        g = pool.get(sid)
        if not g or not g["eligible"]:
            skipped.append((sid, "; ".join(g["blockers"]) if g else
                            "not an eligible graduand for this ceremony"))
            continue
        conn.execute("INSERT OR IGNORE INTO ceremony_invitations (ceremony_id, student_id, "
                     "invited_by) VALUES (?, ?, ?)", (ceremony_id, sid, who.username))
        conn.execute("INSERT OR IGNORE INTO ceremony_rsvps (ceremony_id, student_id, rsvp_status) "
                     "VALUES (?, ?, 'pending')", (ceremony_id, sid))
        emails += ga.notify(conn, [sid], f"You're invited: {row['ceremony_name']}",
                            f"{row['ceremony_name']} on {row['ceremony_date']} at "
                            f"{row['ceremony_time']}, {row['venue']}. Please reply by "
                            f"{row.get('rsvp_deadline') or 'the deadline'} in My Graduation, "
                            "and confirm the name for your certificate.")
        invited.append(sid)
    ga.audit(conn, who, "ceremony", ceremony_id, "invited", {"count": len(invited)})
    return {"invited": invited, "skipped": skipped, "emails": emails}


def send_reminders(conn, as_of=None) -> dict:
    """RSVP and gown-order reminders, at most every three days per graduand."""
    ga.ensure(conn)
    day = date.fromisoformat(ga.iso_date(as_of, "Date") or ga.today())
    soon = (day + timedelta(days=REMIND_DAYS)).isoformat()
    again = (day - timedelta(days=3)).isoformat()
    emails, count = [], 0
    rows = ga.dicts(conn.execute(
        "SELECT i.ceremony_id, i.student_id, i.last_reminded_at, c.ceremony_name, "
        "c.rsvp_deadline, c.gown_order_deadline, r.rsvp_status, (SELECT 1 FROM "
        "ceremony_gown_orders g WHERE g.ceremony_id = i.ceremony_id AND g.student_id = "
        "i.student_id AND COALESCE(g.status, '') <> 'cancelled') AS has_gown FROM "
        "ceremony_invitations i JOIN graduation_ceremonies c ON c.ceremony_id = i.ceremony_id "
        "LEFT JOIN ceremony_rsvps r ON r.ceremony_id = i.ceremony_id AND r.student_id = "
        "i.student_id WHERE COALESCE(c.status, 'scheduled') = 'scheduled'"))
    for r in rows:
        if r["last_reminded_at"] and r["last_reminded_at"][:10] > again:
            continue
        lines = []
        if r["rsvp_status"] in (None, "pending", "interested") and r["rsvp_deadline"] and \
                day.isoformat() <= r["rsvp_deadline"] <= soon:
            lines.append(f"Please reply to your invitation by {r['rsvp_deadline']}.")
        if r["rsvp_status"] == "going" and not r["has_gown"] and r["gown_order_deadline"] and \
                day.isoformat() <= r["gown_order_deadline"] <= soon:
            lines.append(f"Order your gown by {r['gown_order_deadline']}.")
        if lines:
            emails += ga.notify(conn, [r["student_id"]], f"Reminder: {r['ceremony_name']}",
                                "\n".join(lines))
            conn.execute("UPDATE ceremony_invitations SET last_reminded_at = ? WHERE ceremony_id "
                         "= ? AND student_id = ?", (day.isoformat(), r["ceremony_id"],
                                                    r["student_id"]))
            count += 1
    return {"reminded": count, "emails": emails}


# ── RSVPs and tickets ───────────────────────────────────────────────────


def _seats_taken(conn, ceremony_id, except_student=None) -> int:
    return int(conn.execute("SELECT COALESCE(SUM(1 + num_guests), 0) FROM ceremony_rsvps WHERE "
                            "ceremony_id = ? AND rsvp_status = 'going' AND student_id <> ?",
                            (ceremony_id, except_student or "")).fetchone()[0])


def _granted(conn, ceremony_id, student_id) -> int:
    row = conn.execute("SELECT granted FROM ceremony_ticket_requests WHERE ceremony_id = ? AND "
                       "student_id = ?", (ceremony_id, student_id)).fetchone()
    return int(row[0] or 0) if row else 0


def _check_rsvp(conn, who, row, student_id, status, override) -> None:
    _scheduled(row)
    if status not in RSVP_STATUSES:
        raise ValueError("Reply must be going, not_going, interested or pending")
    office = who.is_office and override
    if row.get("rsvp_deadline") and ga.today() > row["rsvp_deadline"] and not office:
        raise ValueError(f"Replies closed on {row['rsvp_deadline']}")
    if status == "not_going":
        return
    report = ge.check(conn, student_id)
    if not report["eligible"]:
        raise ValueError("Not eligible to graduate: " + "; ".join(report["blockers"]))
    if report["conferral"]:
        raise ValueError("This award has already been conferred")
    invited = conn.execute("SELECT 1 FROM ceremony_invitations WHERE ceremony_id = ? AND "
                           "student_id = ?", (row["ceremony_id"], student_id)).fetchone()
    if not (invited or in_cohort(conn, row["ceremony_id"], student_id, report["award"]) or
            office):
        raise ValueError("This ceremony is for a different cohort")


def _clean_guests(guests) -> list[tuple[str, str]]:
    out = []
    for g in guests or []:
        name, needs = (g, "") if isinstance(g, str) else (g[0], g[1] if len(g) > 1 else "")
        name = (name or "").strip()
        if name:
            out.append((name, (needs or "").strip()))
    return out


def _needs(access_needs) -> str:
    items = [n.strip() for n in (access_needs if isinstance(access_needs, (list, tuple))
                                 else str(access_needs or "").split(",")) if n.strip()]
    bad = [n for n in items if n not in ACCESS_NEEDS]
    if bad:
        raise ValueError("Unknown access need(s): " + ", ".join(bad))
    return ",".join(dict.fromkeys(items))


def record_rsvp(conn, who, ceremony_id, student_id, status, *, guests=(), access_needs="",
                notes="", name_pronunciation="", extra_tickets=0, override=False) -> dict:
    """Reply to an invitation. ``guests`` is a list of names (or
    ``(name, needs)``). Returns ``{"rsvp_id", "tickets", "emails"}``."""
    ga.ensure(conn)
    ga.require_self_or_office(who, student_id)
    row = ceremony(conn, ceremony_id)
    _check_rsvp(conn, who, row, student_id, status, override)
    guests = _clean_guests(guests) if status == "going" else []
    allowance = int(row.get("guest_tickets_per_graduand") or 0) + _granted(conn, ceremony_id,
                                                                           student_id)
    if len(guests) > allowance:
        raise ValueError(f"{len(guests)} guests named; the allowance is {allowance}")
    if status == "going":
        free = int(row["capacity"]) - _seats_taken(conn, ceremony_id, student_id)
        if 1 + len(guests) > free:
            raise ValueError(f"The ceremony is full: {free} seat(s) left")
    needs = _needs(access_needs)
    access_notes = "; ".join(p for p in (needs.replace(",", ", "), (notes or "").strip()) if p)
    conn.execute(
        "INSERT INTO ceremony_rsvps (ceremony_id, student_id, rsvp_status, num_guests, "
        "accessibility_notes, name_pronunciation, access_needs, recorded_by) VALUES (?, ?, ?, ?, "
        "?, ?, ?, ?) ON CONFLICT (ceremony_id, student_id) DO UPDATE SET rsvp_status = "
        "excluded.rsvp_status, num_guests = excluded.num_guests, accessibility_notes = "
        "excluded.accessibility_notes, name_pronunciation = excluded.name_pronunciation, "
        "access_needs = excluded.access_needs, recorded_by = excluded.recorded_by, recorded_at "
        "= datetime('now')",
        (ceremony_id, student_id, status, len(guests), access_notes, name_pronunciation or "",
         needs, who.username))
    conn.execute("UPDATE ceremony_guests SET status = 'cancelled' WHERE ceremony_id = ? AND "
                 "student_id = ? AND status = 'issued'", (ceremony_id, student_id))
    tickets = []
    for name, guest_needs in guests:
        ref = f"G{ceremony_id}-{secrets.token_hex(4).upper()}"
        conn.execute("INSERT INTO ceremony_guests (ceremony_id, student_id, guest_name, "
                     "ticket_ref, access_needs) VALUES (?, ?, ?, ?, ?)",
                     (ceremony_id, student_id, name, ref, guest_needs or None))
        tickets.append((name, ref))
    if status == "not_going":
        conn.execute("UPDATE ceremony_ticket_requests SET status = 'withdrawn' WHERE ceremony_id "
                     "= ? AND student_id = ? AND status = 'waiting'", (ceremony_id, student_id))
    elif int(extra_tickets or 0) > 0:
        conn.execute("INSERT INTO ceremony_ticket_requests (ceremony_id, student_id, requested) "
                     "VALUES (?, ?, ?) ON CONFLICT (ceremony_id, student_id) DO UPDATE SET "
                     "requested = excluded.requested, status = 'waiting'",
                     (ceremony_id, student_id, int(extra_tickets)))
    rsvp_id = conn.execute("SELECT rsvp_id FROM ceremony_rsvps WHERE ceremony_id = ? AND "
                           "student_id = ?", (ceremony_id, student_id)).fetchone()[0]
    ga.audit(conn, who, "rsvp", rsvp_id, status, {"guests": len(guests), "needs": needs})
    body = (f"Your reply for {row['ceremony_name']} ({row['ceremony_date']}): "
            f"{status.replace('_', ' ')}.")
    if tickets:
        body += "\nGuest tickets:\n" + "\n".join(f"  {n}: {r}" for n, r in tickets)
    return {"rsvp_id": int(rsvp_id), "tickets": tickets,
            "emails": ga.notify(conn, [student_id], "Graduation reply received", body)}


def guests(conn, ceremony_id, student_id=None) -> list[dict]:
    ga.ensure(conn)
    sql = "SELECT * FROM ceremony_guests WHERE ceremony_id = ? AND status = 'issued'"
    params = [ceremony_id]
    if student_id:
        sql += " AND student_id = ?"
        params.append(student_id)
    return ga.dicts(conn.execute(sql + " ORDER BY student_id, guest_id", params))


def ticket_requests(conn, ceremony_id) -> list[dict]:
    ga.ensure(conn)
    return ga.dicts(conn.execute("SELECT * FROM ceremony_ticket_requests WHERE ceremony_id = ? "
                                 "ORDER BY requested_at", (ceremony_id,)))


def allocate_extra_tickets(conn, who, ceremony_id) -> dict:
    """Share out the spare seats among waiting requests, first come first
    served. Graduands then name the extra guests in their reply."""
    ga.require_office(who)
    row = ceremony(conn, ceremony_id)
    spare = int(row["capacity"]) - _seats_taken(conn, ceremony_id)
    granted, emails = 0, []
    for req in ticket_requests(conn, ceremony_id):
        if req["status"] != "waiting":
            continue
        give = max(0, min(spare, int(req["requested"])))
        status = "granted" if give == req["requested"] else ("partly_granted" if give else
                                                              "declined")
        conn.execute("UPDATE ceremony_ticket_requests SET granted = ?, status = ?, decided_at = ? "
                     "WHERE request_id = ?", (give, status, ga.now(), req["request_id"]))
        spare -= give
        granted += give
        emails += ga.notify(conn, [req["student_id"]], "Extra guest tickets",
                            f"You asked for {req['requested']} extra ticket(s); {give} granted. "
                            "Add the guests' names to your reply.")
    ga.audit(conn, who, "ceremony", ceremony_id, "extra_tickets", {"granted": granted})
    return {"granted": granted, "spare_left": spare, "emails": emails}


# ── on the day ──────────────────────────────────────────────────────────


def check_in(conn, who, ceremony_id, student_id) -> None:
    ga.require(who is not None and who.can_check_in, "Only ceremony staff can check graduands in")
    row = ceremony(conn, ceremony_id)
    _scheduled(row)
    rsvp = conn.execute("SELECT rsvp_status, attended_at FROM ceremony_rsvps WHERE ceremony_id = "
                        "? AND student_id = ?", (ceremony_id, student_id)).fetchone()
    if not rsvp or rsvp[0] != "going":
        raise ValueError(f"{student_id} has not said they are coming to this ceremony")
    if rsvp[1]:
        raise ValueError(f"{student_id} is already checked in")
    conn.execute("UPDATE ceremony_rsvps SET attended_at = ?, checked_in_by = ?, no_show = 0 WHERE "
                 "ceremony_id = ? AND student_id = ?",
                 (ga.now(), who.username, ceremony_id, student_id))
    ga.audit(conn, who, "ceremony", ceremony_id, "checked_in", {"student": student_id})


def undo_check_in(conn, who, ceremony_id, student_id) -> None:
    ga.require(who is not None and who.can_check_in, "Only ceremony staff can do this")
    _scheduled(ceremony(conn, ceremony_id))
    if not conn.execute("UPDATE ceremony_rsvps SET attended_at = NULL, checked_in_by = NULL "
                        "WHERE ceremony_id = ? AND student_id = ? AND attended_at IS NOT NULL",
                        (ceremony_id, student_id)).rowcount:
        raise ValueError("That graduand is not checked in")
    ga.audit(conn, who, "ceremony", ceremony_id, "check_in_undone", {"student": student_id})


def transfer(conn, who, ceremony_id, student_id, to_ceremony_id, reason="") -> None:
    """Move a graduand (e.g. a no-show) to a later ceremony."""
    ga.require_self_or_office(who, student_id)
    new = ceremony(conn, to_ceremony_id)
    _scheduled(new)
    if new["ceremony_date"] < ga.today():
        raise ValueError("Transfer to a ceremony that has not happened yet")
    old = conn.execute("SELECT attended_at FROM ceremony_rsvps WHERE ceremony_id = ? AND "
                       "student_id = ?", (ceremony_id, student_id)).fetchone()
    if not old:
        raise ValueError(f"{student_id} has no reply for that ceremony")
    if old[0]:
        raise ValueError("The graduand attended that ceremony")
    conn.execute("UPDATE ceremony_rsvps SET rsvp_status = 'not_going', transferred_to = ? WHERE "
                 "ceremony_id = ? AND student_id = ?", (to_ceremony_id, ceremony_id, student_id))
    conn.execute("UPDATE ceremony_guests SET status = 'cancelled' WHERE ceremony_id = ? AND "
                 "student_id = ?", (ceremony_id, student_id))
    conn.execute("INSERT OR IGNORE INTO ceremony_invitations (ceremony_id, student_id, "
                 "invited_by) VALUES (?, ?, ?)", (to_ceremony_id, student_id, who.username))
    conn.execute("INSERT OR IGNORE INTO ceremony_rsvps (ceremony_id, student_id, rsvp_status) "
                 "VALUES (?, ?, 'pending')", (to_ceremony_id, student_id))
    ga.audit(conn, who, "ceremony", ceremony_id, "transferred",
             {"student": student_id, "to": to_ceremony_id, "reason": reason})


def complete(conn, who, ceremony_id, render=gc._render_transcript) -> dict:
    """Close the ceremony: confer the award on every checked-in graduand,
    mark the others as no-shows, congratulate those who attended."""
    ga.require_office(who)
    row = ceremony(conn, ceremony_id)
    _scheduled(row)
    if row["ceremony_date"] > ga.today():
        raise ValueError("The ceremony has not happened yet")
    attended = [r[0] for r in conn.execute(
        "SELECT student_id FROM ceremony_rsvps WHERE ceremony_id = ? AND rsvp_status = 'going' "
        "AND attended_at IS NOT NULL ORDER BY student_id", (ceremony_id,))]
    no_shows = [r[0] for r in conn.execute(
        "SELECT student_id FROM ceremony_rsvps WHERE ceremony_id = ? AND rsvp_status = 'going' "
        "AND attended_at IS NULL", (ceremony_id,))]
    conn.execute("UPDATE ceremony_rsvps SET no_show = 1 WHERE ceremony_id = ? AND rsvp_status = "
                 "'going' AND attended_at IS NULL", (ceremony_id,))
    conferred, failed, emails = [], [], []
    for n, sid in enumerate(attended):
        conn.execute(f"SAVEPOINT confer_{n}")
        try:
            result = gc.confer(conn, who, sid, mode="ceremony", ceremony_id=ceremony_id,
                               conferral_date=row["ceremony_date"], render=render)
            conn.execute(f"RELEASE SAVEPOINT confer_{n}")
            conferred.append(result)
            emails += result["emails"]
        except (ValueError, PermissionError) as exc:
            conn.execute(f"ROLLBACK TO SAVEPOINT confer_{n}")
            conn.execute(f"RELEASE SAVEPOINT confer_{n}")
            failed.append((sid, str(exc)))
    conn.execute("UPDATE graduation_ceremonies SET status = 'completed' WHERE ceremony_id = ?",
                 (ceremony_id,))
    for result in conferred:
        emails += _congratulations(conn, row, result.get("student_id"))
    for sid in no_shows:
        emails += ga.notify(conn, [sid], "We missed you at graduation",
                            "Your award can be conferred in absentia, or you can move to a later "
                            "ceremony from My Graduation.")
    ga.audit(conn, who, "ceremony", ceremony_id, "completed",
             {"conferred": len(conferred), "failed": failed, "no_shows": len(no_shows)})
    return {"conferred": conferred, "failed": failed, "no_shows": no_shows, "emails": emails}


CONGRATULATIONS = "student_life/student_lifecycle/graduation_ceremony_completed"


def _congratulations(conn, row, student_id) -> list[tuple]:
    """The "congratulations, graduate" e-mail to one graduand who crossed
    the stage (completing a ceremony happens once, so it is sent once)."""
    if not student_id:
        return []
    s = ga.student(conn, student_id)
    if not s.get("email_address"):
        return []
    from education_system.systems.university.infrastructure.email.template_utils import (
        render_template,
    )
    subject, body = render_template(CONGRATULATIONS, {
        "student_name": s["name"], "ceremony_name": row["ceremony_name"],
        "ceremony_date": row["ceremony_date"], "ceremony_time": row.get("ceremony_time") or "",
        "venue": row.get("venue") or "", "course": s.get("course") or ""})
    return [(s["email_address"], subject, body)] if subject and body else []


def summary(conn, ceremony_id) -> dict:
    row = ceremony(conn, ceremony_id)
    q = lambda sql: conn.execute(sql, (ceremony_id,)).fetchone()[0] or 0  # noqa: E731
    return {
        "ceremony": row, "capacity": int(row["capacity"]),
        "invited": q("SELECT COUNT(*) FROM ceremony_invitations WHERE ceremony_id = ?"),
        "going": q("SELECT COUNT(*) FROM ceremony_rsvps WHERE ceremony_id = ? AND rsvp_status = "
                   "'going'"),
        "seats_taken": _seats_taken(conn, ceremony_id),
        "guests": q("SELECT COUNT(*) FROM ceremony_guests WHERE ceremony_id = ? AND status = "
                    "'issued'"),
        "attended": q("SELECT COUNT(*) FROM ceremony_rsvps WHERE ceremony_id = ? AND attended_at "
                      "IS NOT NULL"),
        "no_shows": q("SELECT COUNT(*) FROM ceremony_rsvps WHERE ceremony_id = ? AND no_show = 1"),
        "conferred": q("SELECT COUNT(*) FROM graduation_conferrals WHERE ceremony_id = ? AND "
                       "status = 'conferred'"),
        "waiting_tickets": q("SELECT COALESCE(SUM(requested), 0) FROM ceremony_ticket_requests "
                             "WHERE ceremony_id = ? AND status = 'waiting'"),
        "cohorts": cohorts(conn, ceremony_id),
    }


# ── gown orders ─────────────────────────────────────────────────────────


def gown_options() -> dict:
    """Sizes and hire fees a graduand chooses from."""
    m = gcm.GownOrderManager
    return {"gown_sizes": list(m.GOWN_SIZES), "hat_sizes": list(m.HAT_SIZES),
            "fees": {"gown": m.GOWN_HIRE_FEE, "hood": m.HOOD_FEE, "hat": m.HAT_FEE}}


def gown_quote(gown_size="", hood_subject="", hat_size="") -> float:
    return gcm.GownOrderManager.quote(gown_size, hood_subject, hat_size)


def _gown_window(conn, who, ceremony_id, student_id) -> dict:
    """The ceremony, if ``student_id`` may order (or change) a gown for it:
    a scheduled ceremony they are going to, before the gown order deadline
    (or the ceremony itself when no deadline is set). The graduation office
    is not held to the deadline."""
    row = ceremony(conn, ceremony_id)
    _scheduled(row)
    reply = conn.execute("SELECT rsvp_status FROM ceremony_rsvps WHERE ceremony_id = ? AND "
                         "student_id = ?", (ceremony_id, student_id)).fetchone()
    if not reply or reply[0] != "going":
        raise ValueError("Reply that you are going to this ceremony before ordering a gown")
    if not who.is_office:
        closes = row.get("gown_order_deadline") or row["ceremony_date"]
        if ga.today() > closes:
            raise ValueError(f"Gown orders for this ceremony closed on {closes}; contact the "
                             "graduation office")
    return row


def order_gown(conn, who, ceremony_id, student_id, *, gown_size, hood_subject="", hat_size="",
               collection_slot="") -> dict:
    """A graduand orders (or changes) their own gown; the graduation office
    can do it for them. Returns the order with its price."""
    ga.require_self_or_office(who, student_id)
    _gown_window(conn, who, ceremony_id, student_id)
    order_id = gcm.GownOrderManager.place(conn, ceremony_id, student_id, gown_size,
                                         hood_subject, hat_size, "", collection_slot)
    order = ga.one(conn, "SELECT * FROM ceremony_gown_orders WHERE order_id = ?", (order_id,))
    ga.audit(conn, who, "gown_order", order_id, "ordered",
             {"gown": order["gown_size"], "hat": order["hat_size"], "hood": order["hood_subject"],
              "cost": order["cost"]})
    return order


def pay_gown_order(conn, who, order_id, method="student_finance_account") -> dict:
    """Pay for a gown order. A graduand pays their own order from their
    student finance account (cash and card are taken at the gown desk by the
    graduation office). Run :func:`after_gown_payment` once committed."""
    order = ga.one(conn, "SELECT * FROM ceremony_gown_orders WHERE order_id = ?", (order_id,))
    if not order:
        raise ValueError("No such gown order")
    ga.require_self_or_office(who, order["student_id"])
    if not who.is_office and method != "student_finance_account":
        raise PermissionError("Pay from your student finance account, or pay at the gown desk")
    row = ceremony(conn, order["ceremony_id"])
    _scheduled(row)
    result = gcm.GownOrderManager.charge(conn, order_id, method, who.username)
    ga.audit(conn, who, "gown_order", order_id, "paid",
             {"amount": result["amount"], "method": method, "payment": result["payment_id"]})
    return result


def after_gown_payment(result, actor) -> None:
    """After the payment is committed: ledger posting, receipt e-mail and
    any low-balance warning."""
    gcm.GownOrderManager.after_payment(result, actor)


def gown_receipt(order) -> str:
    """A receipt for a paid order, as text (shown on screen)."""
    if not order or (order.get("payment_status") or "") != "paid":
        return ""
    method = gcm.GownOrderManager.PAYMENT_METHOD_DISPLAY.get(order.get("payment_method") or "",
                                                            order.get("payment_method") or "")
    return (f"Gown order receipt {order.get('payment_reference') or ''}\n"
            f"Gown {order.get('gown_size') or '—'}, hat {order.get('hat_size') or '—'}, hood "
            f"{order.get('hood_subject') or '—'}\nPaid £{float(order.get('cost') or 0):.2f} by "
            f"{method} on {(order.get('paid_at') or '')[:16]}")


def cancel_gown_order(conn, who, order_id, reason) -> None:
    order = ga.one(conn, "SELECT * FROM ceremony_gown_orders WHERE order_id = ?", (order_id,))
    if not order:
        raise ValueError("No such gown order")
    ga.require_self_or_office(who, order["student_id"])
    if order.get("status") == "cancelled":
        raise ValueError("That order is already cancelled")
    row = ceremony(conn, order["ceremony_id"])
    if row["ceremony_date"] <= ga.today() and not who.is_office:
        raise ValueError("Gown orders can only be cancelled before the ceremony")
    paid = (order.get("payment_status") or "") == "paid"
    conn.execute("UPDATE ceremony_gown_orders SET status = 'cancelled', cancelled_at = ?, "
                 "cancel_reason = ?, payment_status = ? WHERE order_id = ?",
                 (ga.now(), ga.text(reason, "Reason", True),
                  "refund_due" if paid else order.get("payment_status") or "unpaid", order_id))
    ga.audit(conn, who, "gown_order", order_id, "cancelled", {"reason": reason, "paid": paid})


def refund_gown_order(conn, who, order_id) -> dict:
    """Pay back a cancelled, paid order (recorded in ``unified_refunds``;
    post it to the ledger with :func:`post_refund` after commit)."""
    ga.require_office(who)
    order = ga.one(conn, "SELECT * FROM ceremony_gown_orders WHERE order_id = ?", (order_id,))
    if not order or order.get("payment_status") != "refund_due":
        raise ValueError("That order has no refund due")
    amount = float(order.get("cost") or 0)
    now = ga.now()
    rid = conn.execute(
        "INSERT INTO unified_refunds (student_id, refund_reference, source_type, department, "
        "reference_id, reference_type, amount, refund_type, refund_method, reason, status, "
        "refund_date, request_date, processed_by, notes) VALUES (?, ?, 'graduation_gown', "
        "'Graduation', ?, 'payment', ?, 'full', ?, ?, 'processed', ?, ?, ?, ?)",
        (order["student_id"], f"GOWN-{order_id}", str(order.get("finance_payment_id") or ""),
         amount, (order.get("payment_method") or "original").lower(),
         order.get("cancel_reason") or "Gown order cancelled", now, now, who.username,
         f"Gown order {order_id}")).lastrowid
    conn.execute("UPDATE ceremony_gown_orders SET payment_status = 'refunded', refund_id = ? "
                 "WHERE order_id = ?", (rid, order_id))
    ga.audit(conn, who, "gown_order", order_id, "refunded", {"amount": amount, "refund": rid})
    return {"refund_id": int(rid), "amount": amount}


def post_refund(result, actor) -> None:
    if not result or not result.get("refund_id"):
        return
    try:
        from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
        notify_ledger("refund", result["refund_id"], posted_by=actor)
    except Exception:
        pass


def set_gown_deadline(conn, who, ceremony_id, deadline) -> None:
    """When gown orders close (drives the gown reminder)."""
    ga.require_office(who)
    ceremony(conn, ceremony_id)
    day = ga.iso_date(deadline, "Gown order deadline")
    conn.execute("UPDATE graduation_ceremonies SET gown_order_deadline = ? WHERE ceremony_id = ?",
                 (day, ceremony_id))
    ga.audit(conn, who, "ceremony", ceremony_id, "gown_deadline", {"deadline": day})


def my_ceremonies(conn, who, student_id) -> list[dict]:
    """The ceremonies a graduand is invited to or has replied to, with their
    reply, guests, extra-ticket request and gown order (for My Graduation)."""
    ga.ensure(conn)
    ga.require_self_or_office(who, student_id)
    rows = ga.dicts(conn.execute(
        "SELECT c.*, r.rsvp_status, r.num_guests, r.access_needs, r.accessibility_notes, "
        "r.name_pronunciation, r.attended_at, r.no_show, r.transferred_to FROM "
        "graduation_ceremonies c LEFT JOIN ceremony_rsvps r ON r.ceremony_id = c.ceremony_id AND "
        "r.student_id = ? WHERE c.ceremony_id IN (SELECT ceremony_id FROM ceremony_invitations "
        "WHERE student_id = ? UNION SELECT ceremony_id FROM ceremony_rsvps WHERE student_id = ?) "
        "ORDER BY c.ceremony_date", (student_id, student_id, student_id)))
    for row in rows:
        cid = row["ceremony_id"]
        row["guests"] = guests(conn, cid, student_id)
        row["ticket_request"] = ga.one(conn, "SELECT * FROM ceremony_ticket_requests WHERE "
                                             "ceremony_id = ? AND student_id = ?",
                                       (cid, student_id))
        row["gown_order"] = ga.one(conn, "SELECT * FROM ceremony_gown_orders WHERE ceremony_id "
                                         "= ? AND student_id = ?", (cid, student_id))
        row["allowance"] = int(row.get("guest_tickets_per_graduand") or 0) + _granted(
            conn, cid, student_id)
    return rows


def later_ceremonies(conn, after_ceremony_id=None) -> list[dict]:
    """Scheduled ceremonies still to come (transfer targets)."""
    ga.ensure(conn)
    return ga.dicts(conn.execute(
        "SELECT ceremony_id, ceremony_name, ceremony_date, venue FROM graduation_ceremonies WHERE "
        "COALESCE(status, 'scheduled') = 'scheduled' AND ceremony_date >= ? AND ceremony_id <> ? "
        "ORDER BY ceremony_date", (ga.today(), after_ceremony_id or 0)))
