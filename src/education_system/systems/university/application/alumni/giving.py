"""Alumni giving: campaigns, gifts (with receipts and thank-yous), refunds,
Gift Aid declarations and claims, pledges and donor recognition.

All gifts live in ``donations`` (``alumni_id`` = the alumnus); campaign
totals are worked out from the gifts, not kept by hand.

* **Gift Aid** applies only to a gift from an alumnus with a declaration
  valid on the gift date (made on or before it, or covering the four years
  before it) that confirms they pay enough UK tax. Claims are 25% of the
  eligible gifts not claimed before; a refunded gift that was already
  claimed is taken off the next claim.
* **Pledges** promise instalments; each payment is recorded as a gift
  against the pledge and moves the next due date on.
* **Finance**: a recorded gift is posted to Finance after the commit
  (:func:`post_to_finance`).

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.application.alumni import access as aa

METHODS = ("card", "bank_transfer", "cheque", "cash", "direct_debit", "payroll", "other")
FREQUENCIES = {"one_off": 0, "monthly": 1, "quarterly": 3, "annual": 12}
GIFT_AID_RATE = 0.25
RECOGNITION = ((10000, "Chancellor's Circle"), (1000, "Benefactor"), (250, "Supporter"),
               (0.01, "Friend"))


def _fund(who):
    return who is not None and who.is_fundraiser


def gift(conn, donation_id) -> dict:
    aa.ensure(conn)
    row = aa.one(conn, "SELECT * FROM donations WHERE donation_id = ?", (donation_id,))
    if not row:
        raise ValueError("No such gift")
    row["status"] = row.get("status") or "received"
    return row


# ── campaigns ───────────────────────────────────────────────────────────


def campaigns(conn, active_only=False) -> list[dict]:
    aa.ensure(conn)
    rows = aa.dicts(conn.execute(
        "SELECT c.*, COALESCE((SELECT SUM(d.amount) FROM donations d WHERE d.campaign_id = "
        "c.campaign_id AND COALESCE(d.status, 'received') = 'received'), 0) AS raised FROM "
        "fundraising_campaigns c" + (" WHERE COALESCE(c.status, 'active') = 'active'"
                                     if active_only else "") + " ORDER BY c.start_date DESC"))
    for r in rows:
        goal = float(r.get("goal_amount") or 0)
        r["progress_pct"] = round(100 * float(r["raised"]) / goal, 1) if goal else None
    return rows


def save_campaign(conn, who, data, campaign_id=None) -> int:
    aa.ensure(conn)
    aa.require(_fund(who), "Only fundraising staff can manage campaigns")
    fields = {"campaign_name": aa.text(data.get("campaign_name"), "Name", campaign_id is None),
              "description": aa.text(data.get("description"), "Description"),
              "goal_amount": aa.money(data.get("goal_amount") or 0, "Goal"),
              "start_date": aa.iso_date(data.get("start_date"), "Start date",
                                        campaign_id is None),
              "end_date": aa.iso_date(data.get("end_date"), "End date"),
              "category": aa.text(data.get("category"), "Category")}
    fields = {k: v for k, v in fields.items() if k in data or campaign_id is None}
    if fields.get("end_date") and fields.get("start_date") and \
            fields["end_date"] < fields["start_date"]:
        raise ValueError("The campaign must end after it starts")
    if campaign_id:
        conn.execute(f"UPDATE fundraising_campaigns SET {', '.join(f'{k} = ?' for k in fields)} "
                     "WHERE campaign_id = ?", (*fields.values(), campaign_id))
        aa.audit(conn, who, "campaign", campaign_id, "edited")
        return int(campaign_id)
    cid = conn.execute(
        f"INSERT INTO fundraising_campaigns ({', '.join(fields)}, created_by, created_date, "
        f"status) VALUES ({', '.join('?' * len(fields))}, ?, ?, 'active')",
        (*fields.values(), who.username, aa.now())).lastrowid
    aa.audit(conn, who, "campaign", cid, "created")
    return int(cid)


def close_campaign(conn, who, campaign_id) -> None:
    aa.require(_fund(who), "Only fundraising staff can manage campaigns")
    if not conn.execute("UPDATE fundraising_campaigns SET status = 'closed' WHERE campaign_id = "
                        "?", (campaign_id,)).rowcount:
        raise ValueError("No such campaign")
    aa.audit(conn, who, "campaign", campaign_id, "closed")


def _sync_campaign(conn, campaign_id) -> None:
    if campaign_id:
        conn.execute("UPDATE fundraising_campaigns SET current_amount = (SELECT COALESCE(SUM("
                     "amount), 0) FROM donations WHERE campaign_id = ? AND COALESCE(status, "
                     "'received') = 'received') WHERE campaign_id = ?", (campaign_id, campaign_id))


# ── Gift Aid declarations ───────────────────────────────────────────────


def declarations(conn, alumni_id) -> list[dict]:
    aa.ensure(conn)
    return aa.dicts(conn.execute("SELECT * FROM gift_aid_declarations WHERE alumni_id = ? ORDER "
                                 "BY made_on DESC", (alumni_id,)))


def add_declaration(conn, who, alumni_id, *, full_name, house, postcode, method="written",
                    made_on=None, covers_past_four_years=True, taxpayer_confirmed=False) -> int:
    aa.alumnus(conn, alumni_id)
    aa.require_self_or(who, alumni_id, _fund, "Only the donor or fundraising staff can record a "
                                              "Gift Aid declaration")
    if who.alumni_id == alumni_id:
        method = "online"
    if method not in ("written", "oral", "online"):
        raise ValueError("Method must be written, oral or online")
    if not taxpayer_confirmed:
        raise ValueError("The donor must confirm they pay enough UK Income or Capital Gains Tax")
    did = conn.execute(
        "INSERT INTO gift_aid_declarations (alumni_id, full_name, house, postcode, method, "
        "made_on, covers_past_four_years, taxpayer_confirmed, recorded_by) VALUES (?, ?, ?, ?, ?, "
        "?, ?, 1, ?)",
        (alumni_id, aa.text(full_name, "Full name", True), aa.text(house, "House name or number",
                                                                   True),
         aa.text(postcode, "Postcode", True).upper(), method,
         aa.iso_date(made_on, "Made on") or aa.today(), int(bool(covers_past_four_years)),
         who.username)).lastrowid
    aa.audit(conn, who, "gift_aid", alumni_id, "declared", {"declaration": did,
                                                            "method": method})
    return int(did)


def cancel_declaration(conn, who, declaration_id) -> None:
    row = aa.one(conn, "SELECT * FROM gift_aid_declarations WHERE declaration_id = ?",
                 (declaration_id,))
    if not row or row["cancelled_at"]:
        raise ValueError("No such active declaration")
    aa.require_self_or(who, row["alumni_id"], _fund)
    conn.execute("UPDATE gift_aid_declarations SET cancelled_at = ?, cancelled_by = ? WHERE "
                 "declaration_id = ?", (aa.now(), who.username, declaration_id))
    aa.audit(conn, who, "gift_aid", row["alumni_id"], "declaration_cancelled",
             {"declaration": declaration_id})


def declaration_for(conn, alumni_id, on_date) -> dict | None:
    """The declaration that covers a gift made on ``on_date``."""
    day = date.fromisoformat(on_date[:10])
    for d in declarations(conn, alumni_id):
        made = date.fromisoformat(d["made_on"][:10])
        if d["cancelled_at"] and d["cancelled_at"][:10] <= on_date[:10]:
            continue
        earliest = date(made.year - 4, made.month, min(made.day, 28)) \
            if d["covers_past_four_years"] else made
        if earliest <= day:
            return d
    return None


# ── gifts ───────────────────────────────────────────────────────────────


def _receipt_number(conn) -> str:
    year = date.today().year
    n = conn.execute("SELECT COUNT(*) FROM donations WHERE receipt_number LIKE ?",
                     (f"GIFT-{year}-%",)).fetchone()[0]
    while True:
        n += 1
        ref = f"GIFT-{year}-{n:05d}"
        if not conn.execute("SELECT 1 FROM donations WHERE receipt_number = ?",
                            (ref,)).fetchone():
            return ref


def record_gift(conn, who, alumni_id, amount, *, gift_date=None, campaign_id=None,
                method="card", gift_aid=False, notes="", pledge_id=None) -> dict:
    """Record a received gift. Returns ``{"donation_id", "receipt_number",
    "gift_aided", "emails", ...}``; pass it to :func:`post_to_finance`."""
    row = aa.alumnus(conn, alumni_id)
    aa.require(_fund(who), "Only fundraising staff can record gifts")
    amount = aa.money(amount, "Amount")
    if not amount:
        raise ValueError("The gift must be more than zero")
    if method not in METHODS:
        raise ValueError("Method must be one of " + ", ".join(METHODS))
    day = aa.iso_date(gift_date, "Gift date") or aa.today()
    if day > aa.today():
        raise ValueError("A gift cannot be dated in the future")
    if campaign_id and not conn.execute("SELECT 1 FROM fundraising_campaigns WHERE campaign_id "
                                        "= ?", (campaign_id,)).fetchone():
        raise ValueError("No such campaign")
    declaration = declaration_for(conn, alumni_id, day) if gift_aid else None
    if gift_aid and declaration is None:
        raise ValueError("There is no Gift Aid declaration covering this gift")
    receipt = _receipt_number(conn)
    did = conn.execute(
        "INSERT INTO donations (alumni_id, amount, donation_date, campaign_id, payment_method, "
        "notes, donation_type, is_gift_aided, gift_aid_declaration_id, pledge_id, "
        "receipt_number, status, recorded_by, donor_name) VALUES (?, ?, ?, ?, ?, ?, 'gift', ?, "
        "?, ?, ?, 'received', ?, ?)",
        (alumni_id, amount, day, campaign_id, method, notes or None, int(bool(declaration)),
         declaration["declaration_id"] if declaration else None, pledge_id, receipt,
         who.username, row["name"])).lastrowid
    conn.execute("UPDATE alumni SET is_donor = 1 WHERE alumni_id = ?", (alumni_id,))
    _sync_campaign(conn, campaign_id)
    emails = []
    if not (row.get("deceased_at") or row.get("anonymised_at")):     # a receipt is not marketing
        emails = aa.notify(conn, [alumni_id], f"Thank you for your gift ({receipt})",
                           f"Thank you for your gift of £{amount:,.2f} on {day}."
                           + (" We will claim Gift Aid on it." if declaration else ""))
        conn.execute("UPDATE donations SET thanked_at = ?, receipt_sent = 1 WHERE donation_id = "
                     "?", (aa.now(), did))
    aa.audit(conn, who, "gift", did, "recorded", {"alumni": alumni_id, "amount": amount,
                                                   "gift_aid": bool(declaration)})
    return {"donation_id": int(did), "receipt_number": receipt, "amount": amount,
            "alumni_id": alumni_id, "method": method, "gift_aided": bool(declaration),
            "emails": emails}


def post_to_finance(result, actor) -> None:
    """After commit: record the gift as income in Finance."""
    if not result or "donation_id" not in result:
        return
    try:
        from education_system.systems.university.domains.finance.infrastructure.finance_integration import (  # noqa: E501
            record_revenue_to_finance,
        )
        from education_system.systems.university.infrastructure.database.db import transaction
        payment_id = record_revenue_to_finance(
            student_id="EXTERNAL", amount=result["amount"], revenue_category="Donation",
            transaction_source="Alumni Giving", transaction_ref=result["receipt_number"],
            payment_method=result["method"],
            notes=f"Gift {result['receipt_number']} from alumnus {result['alumni_id']}, "
                  f"recorded by {actor}")
        if payment_id:
            with transaction() as conn:
                conn.execute("UPDATE donations SET finance_payment_id = ? WHERE donation_id = ?",
                             (payment_id, result["donation_id"]))
    except Exception:
        pass


def refund_gift(conn, who, donation_id, reason) -> dict:
    row = gift(conn, donation_id)
    aa.require(_fund(who), "Only fundraising staff can refund gifts")
    if row["status"] != "received":
        raise ValueError("That gift is already refunded")
    conn.execute("UPDATE donations SET status = 'refunded', refunded_at = ?, refund_reason = ? "
                 "WHERE donation_id = ?", (aa.now(), aa.text(reason, "Reason", True),
                                           donation_id))
    _sync_campaign(conn, row.get("campaign_id"))
    claimed = bool(row.get("gift_aid_claim_id"))
    aa.audit(conn, who, "gift", donation_id, "refunded", {"reason": reason,
                                                          "gift_aid_claimed": claimed})
    return {"donation_id": donation_id, "gift_aid_to_repay":
            round(float(row["amount"]) * GIFT_AID_RATE, 2) if claimed else 0.0}


def gifts(conn, who, alumni_id=None, campaign_id=None, search=None) -> list[dict]:
    aa.ensure(conn)
    if not _fund(who):
        aa.require(who is not None and who.alumni_id is not None,
                   "Only fundraising staff can see gifts")
        alumni_id = who.alumni_id
    where, params = [], []
    if alumni_id:
        where.append("d.alumni_id = ?")
        params.append(alumni_id)
    if campaign_id:
        where.append("d.campaign_id = ?")
        params.append(campaign_id)
    if search:
        like = f"%{str(search).lower()}%"
        where.append("(LOWER(COALESCE(d.donor_name, '')) LIKE ? OR LOWER(COALESCE("
                     "d.receipt_number, '')) LIKE ? OR LOWER(COALESCE(d.alumni_id, '')) LIKE ?)")
        params += [like] * 3
    return aa.dicts(conn.execute(
        "SELECT d.*, c.campaign_name FROM donations d LEFT JOIN fundraising_campaigns c ON "
        "c.campaign_id = d.campaign_id" + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY d.donation_date DESC, d.donation_id DESC", params))


# ── Gift Aid claims ─────────────────────────────────────────────────────


def build_claim(conn, who, period_from, period_to) -> dict:
    """Draft a claim for eligible, unclaimed gifts in the period, less any
    refunds of gifts already claimed."""
    aa.ensure(conn)
    aa.require(_fund(who), "Only fundraising staff can claim Gift Aid")
    start = aa.iso_date(period_from, "From", True)
    end = aa.iso_date(period_to, "To", True)
    if end < start:
        raise ValueError("The period must end after it starts")
    if conn.execute("SELECT 1 FROM gift_aid_claims WHERE status = 'draft'").fetchone():
        raise ValueError("Submit or delete the existing draft claim first")
    eligible = [g for g in aa.dicts(conn.execute(
        "SELECT * FROM donations WHERE is_gift_aided = 1 AND COALESCE(status, 'received') = "
        "'received' AND gift_aid_claim_id IS NULL AND donation_date BETWEEN ? AND ?",
        (start, end))) if declaration_for(conn, g["alumni_id"], g["donation_date"])]
    refunds = aa.dicts(conn.execute(
        "SELECT * FROM donations WHERE status = 'refunded' AND gift_aid_claim_id IS NOT NULL AND "
        "gift_aid_adjusted_in IS NULL"))
    total = round(sum(float(g["amount"]) for g in eligible), 2)
    adjust = round(sum(float(g["amount"]) for g in refunds) * GIFT_AID_RATE, 2)
    claim = round(total * GIFT_AID_RATE - adjust, 2)
    cid = conn.execute("INSERT INTO gift_aid_claims (period_from, period_to, donations_total, "
                       "claim_total, adjustments_total, gift_count, created_by) VALUES (?, ?, ?, "
                       "?, ?, ?, ?)", (start, end, total, claim, adjust, len(eligible),
                                       who.username)).lastrowid
    for g in eligible:
        conn.execute("UPDATE donations SET gift_aid_claim_id = ? WHERE donation_id = ?",
                     (cid, g["donation_id"]))
    for g in refunds:
        conn.execute("UPDATE donations SET gift_aid_adjusted_in = ? WHERE donation_id = ?",
                     (cid, g["donation_id"]))
    aa.audit(conn, who, "gift_aid_claim", cid, "drafted", {"gifts": len(eligible),
                                                            "claim": claim})
    return {"claim_id": int(cid), "gifts": len(eligible), "donations_total": total,
            "adjustments": adjust, "claim_total": claim}


def delete_draft_claim(conn, who, claim_id) -> None:
    aa.require(_fund(who), "Only fundraising staff can claim Gift Aid")
    row = aa.one(conn, "SELECT status FROM gift_aid_claims WHERE claim_id = ?", (claim_id,))
    if not row or row["status"] != "draft":
        raise ValueError("Only a draft claim can be deleted")
    conn.execute("UPDATE donations SET gift_aid_claim_id = NULL WHERE gift_aid_claim_id = ?",
                 (claim_id,))
    conn.execute("UPDATE donations SET gift_aid_adjusted_in = NULL WHERE gift_aid_adjusted_in = "
                 "?", (claim_id,))
    conn.execute("DELETE FROM gift_aid_claims WHERE claim_id = ?", (claim_id,))
    aa.audit(conn, who, "gift_aid_claim", claim_id, "deleted")


def submit_claim(conn, who, claim_id, hmrc_reference) -> None:
    aa.require(_fund(who), "Only fundraising staff can claim Gift Aid")
    if not conn.execute("UPDATE gift_aid_claims SET status = 'submitted', submitted_at = ?, "
                        "hmrc_reference = ? WHERE claim_id = ? AND status = 'draft'",
                        (aa.now(), aa.text(hmrc_reference, "HMRC reference", True),
                         claim_id)).rowcount:
        raise ValueError("Only a draft claim can be submitted")
    aa.audit(conn, who, "gift_aid_claim", claim_id, "submitted", {"ref": hmrc_reference})


def mark_claim_paid(conn, who, claim_id) -> None:
    aa.require(_fund(who), "Only fundraising staff can claim Gift Aid")
    if not conn.execute("UPDATE gift_aid_claims SET status = 'paid', paid_at = ? WHERE claim_id "
                        "= ? AND status = 'submitted'", (aa.now(), claim_id)).rowcount:
        raise ValueError("Only a submitted claim can be marked paid")
    aa.audit(conn, who, "gift_aid_claim", claim_id, "paid")


def claims(conn) -> list[dict]:
    aa.ensure(conn)
    return aa.dicts(conn.execute("SELECT * FROM gift_aid_claims ORDER BY claim_id DESC"))


# ── pledges ─────────────────────────────────────────────────────────────


def _add_months(day: date, months: int) -> date:
    m = day.month - 1 + months
    return date(day.year + m // 12, m % 12 + 1, min(day.day, 28))


def create_pledge(conn, who, alumni_id, amount, frequency, instalments=1, *, start=None,
                  campaign_id=None) -> int:
    row = aa.alumnus(conn, alumni_id)
    aa.require_self_or(who, alumni_id, _fund)
    if not aa.contactable(row) and who.alumni_id != alumni_id:
        raise ValueError("This alumnus cannot be asked for a pledge")
    if frequency not in FREQUENCIES:
        raise ValueError("Frequency must be one of " + ", ".join(FREQUENCIES))
    instalments = 1 if frequency == "one_off" else int(instalments)
    if instalments < 1 or instalments > 120:
        raise ValueError("Instalments must be 1 to 120")
    first = aa.iso_date(start, "First payment") or aa.today()
    pid = conn.execute("INSERT INTO donation_pledges (alumni_id, campaign_id, amount, frequency, "
                       "instalments, next_due, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (alumni_id, campaign_id, aa.money(amount, "Amount per instalment"),
                        frequency, instalments, first, who.username)).lastrowid
    aa.audit(conn, who, "pledge", pid, "created", {"alumni": alumni_id, "amount": amount,
                                                    "frequency": frequency})
    return int(pid)


def cancel_pledge(conn, who, pledge_id, reason) -> None:
    row = aa.one(conn, "SELECT * FROM donation_pledges WHERE pledge_id = ?", (pledge_id,))
    if not row or row["status"] != "active":
        raise ValueError("No such active pledge")
    aa.require_self_or(who, row["alumni_id"], _fund)
    conn.execute("UPDATE donation_pledges SET status = 'cancelled', cancelled_reason = ? WHERE "
                 "pledge_id = ?", (aa.text(reason, "Reason", True), pledge_id))
    aa.audit(conn, who, "pledge", pledge_id, "cancelled", {"reason": reason})


def record_pledge_payment(conn, who, pledge_id, *, method="direct_debit", paid_on=None,
                          gift_aid=False) -> dict:
    row = aa.one(conn, "SELECT * FROM donation_pledges WHERE pledge_id = ?", (pledge_id,))
    if not row or row["status"] != "active":
        raise ValueError("No such active pledge")
    result = record_gift(conn, who, row["alumni_id"], row["amount"], gift_date=paid_on,
                         campaign_id=row["campaign_id"], method=method, gift_aid=gift_aid,
                         notes=f"Pledge {pledge_id}", pledge_id=pledge_id)
    paid = int(row["paid_instalments"]) + 1
    done = paid >= int(row["instalments"])
    step = FREQUENCIES[row["frequency"]]
    nxt = None if done or not step else _add_months(date.fromisoformat(row["next_due"]),
                                                     step).isoformat()
    conn.execute("UPDATE donation_pledges SET paid_instalments = ?, next_due = ?, status = ? "
                 "WHERE pledge_id = ?", (paid, nxt, "completed" if done else "active",
                                         pledge_id))
    return {**result, "pledge_completed": done, "next_due": nxt}


def pledges(conn, who, alumni_id=None, due_by=None) -> list[dict]:
    aa.ensure(conn)
    if not _fund(who):
        aa.require(who is not None and who.alumni_id is not None, "Not allowed")
        alumni_id = who.alumni_id
    where, params = [], []
    if alumni_id:
        where.append("alumni_id = ?")
        params.append(alumni_id)
    if due_by:
        where.append("status = 'active' AND next_due <= ?")
        params.append(aa.iso_date(due_by, "Due by"))
    return aa.dicts(conn.execute("SELECT * FROM donation_pledges" +
                                 (" WHERE " + " AND ".join(where) if where else "") +
                                 " ORDER BY next_due", params))


def overdue_pledges(conn, as_of=None) -> list[dict]:
    day = aa.iso_date(as_of, "Date") or aa.today()
    late = (date.fromisoformat(day) - timedelta(days=14)).isoformat()
    return aa.dicts(conn.execute("SELECT * FROM donation_pledges WHERE status = 'active' AND "
                                 "next_due < ? ORDER BY next_due", (late,)))


# ── donors ──────────────────────────────────────────────────────────────


def recognition_level(total) -> str | None:
    for threshold, name in RECOGNITION:
        if total >= threshold:
            return name
    return None


def donor_summary(conn, who, alumni_id) -> dict:
    aa.alumnus(conn, alumni_id)
    aa.require_self_or(who, alumni_id, _fund)
    total = conn.execute("SELECT COALESCE(SUM(amount), 0), COUNT(*), MAX(donation_date) FROM "
                         "donations WHERE alumni_id = ? AND COALESCE(status, 'received') = "
                         "'received'", (alumni_id,)).fetchone()
    return {"total": round(float(total[0]), 2), "gifts": total[1], "last_gift": total[2],
            "recognition": recognition_level(float(total[0])),
            "gift_aid_declared": declaration_for(conn, alumni_id, aa.today()) is not None,
            "active_pledges": [p for p in pledges(conn, who, alumni_id) if p["status"] == "active"]}
