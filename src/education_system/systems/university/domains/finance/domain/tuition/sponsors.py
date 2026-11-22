"""Sponsor organisations, their purchase orders and per-student
sponsorship agreements, and the sponsor's share of a tuition charge.

An agreement pays a percentage of each year's tuition or a fixed amount a
year, for a range of academic years, optionally up to a total cap. At
charge time (``charging``) the sponsor's share is invoiced to the sponsor
and only the remainder is charged to the student.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import re

from education_system.systems.university.domains.finance.domain.tuition import access

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SPONSOR_FIELDS = ("contact_name", "contact_email", "contact_phone", "billing_address",
                  "vat_number", "payment_terms_days", "active")


# ── organisations ───────────────────────────────────────────────────────


def _clean_sponsor(fields: dict) -> dict:
    out = {k: access.text(fields.get(k), k.replace("_", " ")) for k in SPONSOR_FIELDS
           if k in fields and k not in ("payment_terms_days", "active")}
    email = out.get("contact_email")
    if email and not _EMAIL.match(email):
        raise ValueError("The contact e-mail does not look like an e-mail address")
    if "payment_terms_days" in fields and fields["payment_terms_days"] not in (None, ""):
        try:
            days = int(fields["payment_terms_days"])
        except (TypeError, ValueError):
            raise ValueError("Payment terms are a number of days") from None
        if not 0 <= days <= 365:
            raise ValueError("Payment terms are between 0 and 365 days")
        out["payment_terms_days"] = days
    if "active" in fields:
        out["active"] = 1 if fields["active"] else 0
    return out


def add_sponsor(conn, who, name, **fields) -> int:
    access.ensure(conn)
    access.require(conn, who, access.SPONSORS)
    name = access.text(name, "Sponsor name", True)
    if conn.execute("SELECT 1 FROM sponsors WHERE name = ?", (name,)).fetchone():
        raise ValueError(f"There is already a sponsor called {name}")
    clean = _clean_sponsor(fields)
    cols = ["name", "created_by", *clean]
    new_id = conn.execute(
        f"INSERT INTO sponsors ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",  # nosec B608
        (name, who.username, *clean.values())).lastrowid
    access.audit(conn, who.username, "sponsor.added", "sponsor", new_id,
                 detail={"name": name, **clean})
    return int(new_id)


def update_sponsor(conn, who, sponsor_id, **fields) -> None:
    access.ensure(conn)
    access.require(conn, who, access.SPONSORS)
    before = get_sponsor(conn, sponsor_id)
    clean = _clean_sponsor(fields)
    if not clean:
        return
    sets = ", ".join(f"{k} = ?" for k in clean)  # keys come from SPONSOR_FIELDS only
    conn.execute(f"UPDATE sponsors SET {sets} WHERE sponsor_id = ?",  # nosec B608
                 (*clean.values(), int(sponsor_id)))
    access.audit(conn, who.username, "sponsor.updated", "sponsor", sponsor_id,
                 detail={"changes": clean, "was": {k: before.get(k) for k in clean}})


def get_sponsor(conn, sponsor_id) -> dict:
    access.ensure(conn)
    row = access.one(conn.execute("SELECT * FROM sponsors WHERE sponsor_id = ?",
                                  (int(sponsor_id),)))
    if not row:
        raise ValueError(f"No sponsor {sponsor_id}")
    return row


def sponsors(conn, active_only=False) -> list[dict]:
    access.ensure(conn)
    sql = "SELECT * FROM sponsors" + (" WHERE active = 1" if active_only else "")
    return access.dicts(conn.execute(sql + " ORDER BY name"))


def find_sponsor(conn, name) -> dict | None:
    access.ensure(conn)
    return access.one(conn.execute("SELECT * FROM sponsors WHERE name = ?",
                                   (str(name or "").strip(),)))


# ── purchase orders ─────────────────────────────────────────────────────


def add_po(conn, who, sponsor_id, po_number, *, academic_year=None, amount_limit=None,
           valid_to=None) -> int:
    access.ensure(conn)
    access.require(conn, who, access.SPONSORS)
    get_sponsor(conn, sponsor_id)
    number = access.text(po_number, "PO number", True)
    if conn.execute("SELECT 1 FROM sponsor_purchase_orders WHERE sponsor_id = ? AND "
                    "po_number = ?", (int(sponsor_id), number)).fetchone():
        raise ValueError(f"PO {number} is already recorded for this sponsor")
    limit = None if amount_limit in (None, "") else access.money(amount_limit, "PO limit")
    year = access.year_label(academic_year) if academic_year else None
    new_id = conn.execute(
        "INSERT INTO sponsor_purchase_orders (sponsor_id, po_number, academic_year, "
        "amount_limit, valid_to, created_by) VALUES (?, ?, ?, ?, ?, ?)",
        (int(sponsor_id), number, year, limit, valid_to or None, who.username)).lastrowid
    access.audit(conn, who.username, "sponsor_po.added", "sponsor_purchase_order", new_id,
                 detail={"sponsor_id": sponsor_id, "po_number": number, "limit": limit,
                         "academic_year": year})
    return int(new_id)


def close_po(conn, who, po_id) -> None:
    access.ensure(conn)
    access.require(conn, who, access.SPONSORS)
    conn.execute("UPDATE sponsor_purchase_orders SET status = 'closed' WHERE po_id = ?",
                 (int(po_id),))
    access.audit(conn, who.username, "sponsor_po.closed", "sponsor_purchase_order", po_id)


def purchase_orders(conn, sponsor_id=None) -> list[dict]:
    access.ensure(conn)
    sql = ("SELECT p.*, s.name AS sponsor FROM sponsor_purchase_orders p JOIN sponsors s ON "
           "s.sponsor_id = p.sponsor_id")
    params: list = []
    if sponsor_id is not None:
        sql += " WHERE p.sponsor_id = ?"
        params.append(int(sponsor_id))
    return access.dicts(conn.execute(sql + " ORDER BY s.name, p.po_number", params))


# ── agreements ──────────────────────────────────────────────────────────


def _agreement_values(basis, value, start_year, end_year, cap_amount):
    if basis not in ("percent", "amount"):
        raise ValueError("Basis is percent or amount")
    value = access.money(value, "Value", allow_zero=False)
    if basis == "percent" and value > 100:
        raise ValueError("A percentage is at most 100")
    start, end = access.year_start(start_year), access.year_start(end_year or start_year)
    if end < start:
        raise ValueError("The last year is before the first")
    cap = None if cap_amount in (None, "") else access.money(cap_amount, "Cap",
                                                             allow_zero=False)
    return value, start, end, cap


def add_agreement(conn, who, sponsor_id, student_id, *, basis, value, start_year,
                  end_year=None, cap_amount=None, po_id=None, notes=None, source="manual",
                  source_ref=None) -> int:
    access.ensure(conn)
    access.require(conn, who, access.SPONSORS)
    sponsor = get_sponsor(conn, sponsor_id)
    if not sponsor["active"]:
        raise ValueError(f"{sponsor['name']} is not an active sponsor")
    access.student_row(conn, student_id)
    value, start, end, cap = _agreement_values(basis, value, start_year, end_year, cap_amount)
    if po_id not in (None, ""):
        po = conn.execute("SELECT sponsor_id FROM sponsor_purchase_orders WHERE po_id = ?",
                          (int(po_id),)).fetchone()
        if not po or int(po[0]) != int(sponsor_id):
            raise ValueError("That PO does not belong to this sponsor")
    clash = conn.execute(
        "SELECT agreement_id FROM sponsorship_agreements WHERE student_id = ? AND status = "
        "'active' AND NOT (end_year < ? OR start_year > ?)", (str(student_id), start, end)
    ).fetchone()
    if clash:
        raise ValueError(f"Agreement #{clash[0]} already covers part of these years; end it "
                         "first")
    new_id = conn.execute(
        "INSERT INTO sponsorship_agreements (sponsor_id, student_id, basis, value, start_year, "
        "end_year, cap_amount, po_id, source, source_ref, notes, created_by) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (int(sponsor_id), str(student_id), basis, value, start, end, cap,
         int(po_id) if po_id not in (None, "") else None, source, source_ref,
         access.text(notes, "Notes"), who.username)).lastrowid
    access.audit(conn, who.username, "sponsorship.agreed", "sponsorship_agreement", new_id,
                 student_id=student_id,
                 detail={"sponsor": sponsor["name"], "basis": basis, "value": value,
                         "years": [start, end], "cap": cap, "source": source,
                         "source_ref": source_ref})
    return int(new_id)


def end_agreement(conn, who, agreement_id, reason, *, cancel=False) -> None:
    access.ensure(conn)
    access.require(conn, who, access.SPONSORS)
    reason = access.text(reason, "Reason", True)
    row = get_agreement(conn, agreement_id)
    if row["status"] != "active":
        raise ValueError(f"Agreement #{agreement_id} is already {row['status']}")
    status = "cancelled" if cancel else "ended"
    conn.execute("UPDATE sponsorship_agreements SET status = ?, notes = TRIM(COALESCE(notes, "
                 "'') || ' ' || ?) WHERE agreement_id = ?",
                 (status, f"[{status} {access.today()}: {reason}]", int(agreement_id)))
    access.audit(conn, who.username, f"sponsorship.{status}", "sponsorship_agreement",
                 agreement_id, student_id=row["student_id"], detail={"reason": reason})


def get_agreement(conn, agreement_id) -> dict:
    access.ensure(conn)
    row = access.one(conn.execute(
        "SELECT a.*, s.name AS sponsor, p.po_number FROM sponsorship_agreements a JOIN "
        "sponsors s ON s.sponsor_id = a.sponsor_id LEFT JOIN sponsor_purchase_orders p ON "
        "p.po_id = a.po_id WHERE a.agreement_id = ?", (int(agreement_id),)))
    if not row:
        raise ValueError(f"No sponsorship agreement {agreement_id}")
    return row


def agreements(conn, *, student_id=None, sponsor_id=None, status=None) -> list[dict]:
    access.ensure(conn)
    sql = ("SELECT a.*, s.name AS sponsor, p.po_number, TRIM(COALESCE(st.first_name, '') || "
           "' ' || COALESCE(st.last_name, '')) AS student_name FROM sponsorship_agreements a "
           "JOIN sponsors s ON s.sponsor_id = a.sponsor_id LEFT JOIN sponsor_purchase_orders p "
           "ON p.po_id = a.po_id LEFT JOIN students st ON st.student_id = a.student_id "
           "WHERE 1 = 1")
    params: list = []
    for column, value in (("a.student_id", student_id), ("a.sponsor_id", sponsor_id),
                          ("a.status", status)):
        if value is not None:
            sql += f" AND {column} = ?"
            params.append(value)
    rows = access.dicts(conn.execute(sql + " ORDER BY a.agreement_id DESC", params))
    for r in rows:
        r["billed"] = billed_to_date(conn, r["agreement_id"])
    return rows


def active_agreement(conn, student_id, academic_year) -> dict | None:
    access.ensure(conn)
    start = access.year_start(academic_year)
    row = access.one(conn.execute(
        "SELECT a.*, s.name AS sponsor, s.active AS sponsor_active, p.po_number FROM "
        "sponsorship_agreements a JOIN sponsors s ON s.sponsor_id = a.sponsor_id LEFT JOIN "
        "sponsor_purchase_orders p ON p.po_id = a.po_id WHERE a.student_id = ? AND a.status = "
        "'active' AND a.start_year <= ? AND a.end_year >= ? ORDER BY a.agreement_id DESC "
        "LIMIT 1", (str(student_id), start, start)))
    return row if row and row["sponsor_active"] else None


def billed_to_date(conn, agreement_id) -> float:
    total = conn.execute("SELECT COALESCE(SUM(l.amount), 0) FROM sponsor_invoice_lines l JOIN "
                         "sponsor_invoices i ON i.invoice_id = l.invoice_id WHERE "
                         "l.agreement_id = ? AND i.status != 'cancelled'",
                         (int(agreement_id),)).fetchone()[0]
    return round(float(total or 0), 2)


def sponsor_share(conn, agreement: dict | None, gross: float) -> float:
    """The sponsor's part of a year's tuition of ``gross`` under
    ``agreement`` (0 without one), never more than the gross or what is left
    under the cap."""
    if not agreement or gross <= 0:
        return 0.0
    if agreement["basis"] == "percent":
        share = gross * float(agreement["value"]) / 100
    else:
        share = float(agreement["value"])
    share = min(share, gross)
    if agreement.get("cap_amount") is not None:
        left = float(agreement["cap_amount"]) - billed_to_date(conn, agreement["agreement_id"])
        share = min(share, max(left, 0.0))
    return round(max(share, 0.0), 2)
