"""Intellectual property: disclosure → technology-transfer assessment →
protection (filing, with its deadlines) or release → licences → revenue
shared between inventors, department and university.

* Disclosures list every inventor with a contribution; contributions add up
  to 100%. The person disclosing must be one of them.
* Filing a patent sets the 12-month priority deadline and the 30-month
  national-phase deadline.
* Licence income is split by :data:`REVENUE_BANDS` (cumulative per
  disclosure), and the inventors' share by their contribution.

Disclosures live on ``ip_disclosures`` / ``ip_inventors`` / ``ip_licenses``
/ ``ip_revenue_shares``. Functions take an open connection and do not
commit; the caller does.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.application.research import access as ra

TYPES = ("Patent", "Copyright", "Software", "Design", "Trademark", "Know-how", "Other")
STATUSES = ("draft", "submitted", "evaluating", "protect", "filed", "licensed", "released",
            "abandoned")
DECISIONS = ("evaluating", "protect", "release", "abandon")
LICENCE_TYPES = ("exclusive", "non_exclusive", "option", "assignment")
#: (income up to £, inventors %, department %, university %) — cumulative per disclosure.
REVENUE_BANDS = ((100_000, 50, 25, 25), (500_000, 33.33, 33.33, 33.34),
                 (None, 25, 25, 50))
_FIELDS = ("title", "description", "ip_type", "development_stage", "funding_source",
           "department", "commercial_route", "project_id", "jurisdiction")


def disclosure(conn, disclosure_id) -> dict:
    ra.ensure(conn)
    row = ra.one(conn, "SELECT * FROM ip_disclosures WHERE disclosure_id = ?", (disclosure_id,))
    if not row:
        raise ValueError("No such IP disclosure")
    return row


def inventors(conn, disclosure_id) -> list[dict]:
    return ra.dicts(conn.execute("SELECT user_id AS username, contribution_percentage, "
                                 "is_primary FROM ip_inventors WHERE disclosure_id = ? ORDER BY "
                                 "is_primary DESC, contribution_percentage DESC",
                                 (disclosure_id,)))


def _is_inventor(conn, who, disclosure_id) -> bool:
    return conn.execute("SELECT 1 FROM ip_inventors WHERE disclosure_id = ? AND user_id = ?",
                        (disclosure_id, who.username)).fetchone() is not None


def can_see(conn, who, row) -> bool:
    return who.is_tto or row.get("created_by") == who.username or \
        _is_inventor(conn, who, row["disclosure_id"])


def _clean(conn, data) -> dict:
    out = {}
    for key in _FIELDS:
        if key not in data:
            continue
        value = data[key]
        if key == "ip_type" and value not in TYPES:
            raise ValueError("Type must be one of " + ", ".join(TYPES))
        if key == "project_id":
            value = int(value) if value not in (None, "") else None
        else:
            value = ra.text(value, key)
        out[key] = value
    return out


def _check_inventors(conn, people) -> list[tuple[str, float]]:
    out, seen = [], set()
    for username, pct in people:
        username = ra.staff_ref(conn, username, "Inventor")
        if username in seen:
            raise ValueError(f"{username} is listed twice")
        seen.add(username)
        pct = float(pct)
        if pct <= 0:
            raise ValueError("Every inventor needs a contribution above 0%")
        out.append((username, pct))
    if not out:
        raise ValueError("List at least one inventor")
    if abs(sum(p for _, p in out) - 100) > 0.01:
        raise ValueError("Inventor contributions must add up to 100%")
    return out


def _write_inventors(conn, disclosure_id, people) -> None:
    conn.execute("DELETE FROM ip_inventors WHERE disclosure_id = ?", (disclosure_id,))
    lead = max(people, key=lambda p: p[1])[0]
    for username, pct in people:
        conn.execute("INSERT INTO ip_inventors (disclosure_id, user_id, contribution_percentage, "
                     "is_primary) VALUES (?, ?, ?, ?)",
                     (disclosure_id, username, pct, int(username == lead)))
    conn.execute("UPDATE ip_disclosures SET inventor_id = ? WHERE disclosure_id = ?",
                 (lead, disclosure_id))


def _reference(conn) -> str:
    year = date.today().year
    n = conn.execute("SELECT COUNT(*) FROM ip_disclosures WHERE reference LIKE ?",
                     (f"IP-{year}-%",)).fetchone()[0]
    while True:
        n += 1
        ref = f"IP-{year}-{n:03d}"
        if not conn.execute("SELECT 1 FROM ip_disclosures WHERE reference = ?",
                            (ref,)).fetchone():
            return ref


def create(conn, who, data, people) -> int:
    ra.ensure(conn)
    ra.require_staff(who)
    fields = _clean(conn, {"ip_type": "Patent", **data})
    if not fields.get("title"):
        raise ValueError("Title is required")
    people = _check_inventors(conn, people)
    if who.username not in {u for u, _ in people} and not who.is_tto:
        raise ValueError("You must be one of the inventors (or ask technology transfer)")
    fields.setdefault("department", ra.department_of(conn, who.username) or None)
    cols = ["reference", "status", "created_by", *fields]
    did = conn.execute(
        f"INSERT INTO ip_disclosures ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [_reference(conn), "draft", who.username, *fields.values()]).lastrowid
    _write_inventors(conn, did, people)
    ra.audit(conn, who, "ip", did, "created")
    return int(did)


def update(conn, who, disclosure_id, data, people=None) -> None:
    row = disclosure(conn, disclosure_id)
    early = row["status"] in ("draft", "submitted")
    ra.require(who.is_tto or (early and _is_inventor(conn, who, disclosure_id)),
               "Only an inventor can edit a disclosure before it is assessed")
    fields = _clean(conn, data)
    if fields:
        conn.execute(f"UPDATE ip_disclosures SET {', '.join(f'{k} = ?' for k in fields)}, "
                     "updated_at = ? WHERE disclosure_id = ?",
                     (*fields.values(), ra.now(), disclosure_id))
    if people is not None:
        _write_inventors(conn, disclosure_id, _check_inventors(conn, people))
    ra.audit(conn, who, "ip", disclosure_id, "edited",
             {"fields": sorted(fields), "inventors": people is not None})


def submit(conn, who, disclosure_id) -> list:
    row = disclosure(conn, disclosure_id)
    ra.require(_is_inventor(conn, who, disclosure_id), "Only an inventor can submit this")
    if row["status"] != "draft":
        raise ValueError("Only a draft can be submitted")
    if not row.get("description"):
        raise ValueError("Describe the invention before submitting")
    conn.execute("UPDATE ip_disclosures SET status = 'submitted', submitted_date = ?, "
                 "updated_at = ? WHERE disclosure_id = ?", (ra.today(), ra.now(), disclosure_id))
    ra.audit(conn, who, "ip", disclosure_id, "submitted")
    return ra.notify(conn, ra.holders(conn, "tto") or ra.holders(conn, "research_office"),
                     f"New IP disclosure {row['reference']}", f"{row['title']} was disclosed.")


def assess(conn, who, disclosure_id, decision, comments) -> list:
    row = disclosure(conn, disclosure_id)
    ra.require(who.is_tto, "Only technology transfer can assess disclosures")
    if row["status"] not in ("submitted", "evaluating"):
        raise ValueError("Only a submitted disclosure can be assessed")
    if decision not in DECISIONS:
        raise ValueError("Decision must be one of " + ", ".join(DECISIONS))
    status = {"release": "released", "abandon": "abandoned"}.get(decision, decision)
    conn.execute("UPDATE ip_disclosures SET status = ?, reviewed_by = ?, review_date = ?, "
                 "review_comments = ?, updated_at = ? WHERE disclosure_id = ?",
                 (status, who.username, ra.today(), ra.text(comments, "Comments", True),
                  ra.now(), disclosure_id))
    ra.audit(conn, who, "ip", disclosure_id, "assessed", {"decision": decision})
    return ra.notify(conn, [i["username"] for i in inventors(conn, disclosure_id)],
                     f"IP disclosure {row['reference']}: {decision}", comments)


def record_filing(conn, who, disclosure_id, filing_date, application_number,
                  jurisdiction="GB") -> None:
    row = disclosure(conn, disclosure_id)
    ra.require(who.is_tto, "Only technology transfer records filings")
    if row["status"] not in ("protect", "filed"):
        raise ValueError("Decide to protect the disclosure before recording a filing")
    filed = ra.iso_date(filing_date, "Filing date", True)
    conn.execute("UPDATE ip_disclosures SET status = 'filed', filing_date = ?, "
                 "application_number = ?, jurisdiction = ?, updated_at = ? WHERE "
                 "disclosure_id = ?",
                 (filed, ra.text(application_number, "Application number", True),
                  jurisdiction or None, ra.now(), disclosure_id))
    if row.get("ip_type") == "Patent":
        day = date.fromisoformat(filed)
        for kind, months in (("Priority year ends (PCT / overseas filing)", 12),
                             ("PCT national phase entry", 30)):
            _add_deadline(conn, disclosure_id, kind, _months_after(day, months))
    ra.audit(conn, who, "ip", disclosure_id, "filed", {"date": filed})


def _months_after(day: date, months: int) -> str:
    month = day.month - 1 + months
    year, month = day.year + month // 12, month % 12 + 1
    for d in (day.day, 30, 29, 28):
        try:
            return date(year, month, d).isoformat()
        except ValueError:
            continue
    return date(year, month, 28).isoformat()


def _add_deadline(conn, disclosure_id, kind, due, note=None) -> int:
    return int(conn.execute("INSERT INTO ip_deadlines (disclosure_id, kind, due_date, note) "
                            "VALUES (?, ?, ?, ?)", (disclosure_id, kind, due, note)).lastrowid)


def add_deadline(conn, who, disclosure_id, kind, due_date, note="") -> int:
    disclosure(conn, disclosure_id)
    ra.require(who.is_tto, "Only technology transfer manages IP deadlines")
    return _add_deadline(conn, disclosure_id, ra.text(kind, "What is due", True),
                         ra.iso_date(due_date, "Due date", True), note or None)


def complete_deadline(conn, who, deadline_id, note="") -> None:
    ra.require(who.is_tto, "Only technology transfer manages IP deadlines")
    if not conn.execute("UPDATE ip_deadlines SET done_at = ?, done_by = ?, note = COALESCE(?, "
                        "note) WHERE deadline_id = ? AND done_at IS NULL",
                        (ra.now(), who.username, note or None, deadline_id)).rowcount:
        raise ValueError("No such open deadline")


def deadlines_due(conn, days=60, as_of=None) -> list[dict]:
    ra.ensure(conn)
    day = date.fromisoformat(ra.iso_date(as_of, "Date") or ra.today())
    return ra.dicts(conn.execute(
        "SELECT d.*, i.reference, i.title FROM ip_deadlines d JOIN ip_disclosures i ON "
        "i.disclosure_id = d.disclosure_id WHERE d.done_at IS NULL AND d.due_date <= ? ORDER BY "
        "d.due_date", ((day + timedelta(days=int(days))).isoformat(),)))


# ── licences and revenue ────────────────────────────────────────────────


def add_licence(conn, who, disclosure_id, licensee, licence_type, start_date, *, end_date=None,
                royalty_rate=0, annual_fee=0, territory="worldwide", notes="") -> int:
    row = disclosure(conn, disclosure_id)
    ra.require(who.is_tto, "Only technology transfer manages licences")
    if row["status"] in ("draft", "submitted", "abandoned"):
        raise ValueError("Assess the disclosure before licensing it")
    if licence_type not in LICENCE_TYPES:
        raise ValueError("Licence type must be one of " + ", ".join(LICENCE_TYPES))
    start = ra.iso_date(start_date, "Start date", True)
    end = ra.iso_date(end_date, "End date")
    if end and end <= start:
        raise ValueError("The licence must end after it starts")
    if licence_type in ("exclusive", "assignment") and conn.execute(
            "SELECT 1 FROM ip_licenses WHERE disclosure_id = ? AND status = 'active' AND "
            "license_type IN ('exclusive', 'assignment')", (disclosure_id,)).fetchone():
        raise ValueError("There is already an active exclusive licence or assignment")
    lid = conn.execute("INSERT INTO ip_licenses (disclosure_id, licensee_name, license_type, "
                       "royalty_rate, territory, start_date, end_date, annual_fee, notes) VALUES "
                       "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (disclosure_id, ra.text(licensee, "Licensee", True), licence_type,
                        float(royalty_rate or 0), territory or "worldwide", start, end,
                        ra.money(annual_fee or 0, "Annual fee"), notes or None)).lastrowid
    conn.execute("UPDATE ip_disclosures SET status = 'licensed', updated_at = ? WHERE "
                 "disclosure_id = ?", (ra.now(), disclosure_id))
    if end:
        _add_deadline(conn, disclosure_id, f"Licence to {licensee} ends", end)
    ra.audit(conn, who, "ip", disclosure_id, "licensed", {"licensee": licensee})
    return int(lid)


def end_licence(conn, who, license_id, reason) -> None:
    ra.require(who.is_tto, "Only technology transfer manages licences")
    if not conn.execute("UPDATE ip_licenses SET status = 'terminated', notes = TRIM(COALESCE("
                        "notes, '') || ' Ended: ' || ?), updated_at = datetime('now') WHERE "
                        "license_id = ? AND status = 'active'",
                        (ra.text(reason, "Reason", True), license_id)).rowcount:
        raise ValueError("No such active licence")


def split(earlier_total: float, amount: float) -> dict:
    """Split ``amount`` of new income given ``earlier_total`` already
    received on the same disclosure, across the bands."""
    shares = {"inventors": 0.0, "department": 0.0, "university": 0.0}
    position, left = float(earlier_total), float(amount)
    for ceiling, inv, dept, uni in REVENUE_BANDS:
        upper = float("inf") if ceiling is None else ceiling
        if left > 0 and position < upper:
            part = min(left, upper - position)
            shares["inventors"] += part * inv / 100
            shares["department"] += part * dept / 100
            shares["university"] += part * uni / 100
            left -= part
            position += part
    return {k: round(v, 2) for k, v in shares.items()}


def record_revenue(conn, who, license_id, period, amount, payment_date=None) -> int:
    ra.require(who.is_tto, "Only technology transfer records licence income")
    lic = ra.one(conn, "SELECT * FROM ip_licenses WHERE license_id = ?", (license_id,))
    if not lic:
        raise ValueError("No such licence")
    amount = ra.money(amount, "Income")
    if not amount:
        raise ValueError("Income must be more than zero")
    earlier = conn.execute("SELECT COALESCE(SUM(r.total_revenue), 0) FROM ip_revenue_shares r "
                           "JOIN ip_licenses l ON l.license_id = r.license_id WHERE "
                           "l.disclosure_id = ?", (lic["disclosure_id"],)).fetchone()[0]
    shares = split(float(earlier), amount)
    rid = conn.execute("INSERT INTO ip_revenue_shares (license_id, period, total_revenue, "
                       "university_share, inventor_share, department_share, payment_date, "
                       "status) VALUES (?, ?, ?, ?, ?, ?, ?, 'allocated')",
                       (license_id, ra.text(period, "Period", True), amount,
                        shares["university"], shares["inventors"], shares["department"],
                        ra.iso_date(payment_date, "Payment date"))).lastrowid
    people = inventors(conn, lic["disclosure_id"])
    paid = 0.0
    for n, person in enumerate(people):
        last = n == len(people) - 1
        each = round(shares["inventors"] - paid if last else
                     shares["inventors"] * float(person["contribution_percentage"]) / 100, 2)
        paid += each
        conn.execute("INSERT INTO ip_inventor_payments (revenue_id, username, amount) VALUES "
                     "(?, ?, ?)", (rid, person["username"], each))
    ra.audit(conn, who, "ip", lic["disclosure_id"], "income", {"amount": amount, **shares})
    return int(rid)


# ── lists ───────────────────────────────────────────────────────────────


def listing(conn, who, status=None, search=None) -> list[dict]:
    ra.ensure(conn)
    rows = ra.dicts(conn.execute("SELECT * FROM ip_disclosures ORDER BY disclosure_id DESC"))
    needle = (search or "").lower()
    out = []
    for row in rows:
        if not can_see(conn, who, row) or (status and row.get("status") != status):
            continue
        hay = " ".join(str(row.get(k) or "") for k in ("reference", "title", "department",
                                                         "ip_type"))
        if not needle or needle in hay.lower():
            out.append(row)
    return out


def record(conn, who, disclosure_id) -> dict:
    row = disclosure(conn, disclosure_id)
    ra.require(can_see(conn, who, row), "You cannot see this disclosure")
    row["inventors"] = inventors(conn, disclosure_id)
    row["licences"] = ra.dicts(conn.execute("SELECT * FROM ip_licenses WHERE disclosure_id = ? "
                                            "ORDER BY license_id", (disclosure_id,)))
    row["revenue"] = ra.dicts(conn.execute(
        "SELECT r.* FROM ip_revenue_shares r JOIN ip_licenses l ON l.license_id = r.license_id "
        "WHERE l.disclosure_id = ? ORDER BY r.revenue_id", (disclosure_id,)))
    if not who.is_tto:      # inventors see only their own payments
        for rev in row["revenue"]:
            rev["mine"] = sum(r[0] for r in conn.execute(
                "SELECT amount FROM ip_inventor_payments WHERE revenue_id = ? AND username = ?",
                (rev["revenue_id"], who.username)))
    row["deadlines"] = ra.dicts(conn.execute("SELECT * FROM ip_deadlines WHERE disclosure_id = ? "
                                             "ORDER BY due_date", (disclosure_id,)))
    row["history"] = ra.history(conn, "ip", disclosure_id)
    return row
