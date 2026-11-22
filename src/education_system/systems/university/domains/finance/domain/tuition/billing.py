"""Sponsor invoices, sponsor payments and their allocation, sponsor
letters, and the refund requests tuition credits raise.

A sponsor's share of each tuition charge is a line on that sponsor's draft
invoice for the academic year (one draft per sponsor, year and PO). Finance
issues the invoice (it then gets its number and due date), prints it or a
sponsor letter as a PDF, and allocates the sponsor's payments to issued
invoices. A credit (a withdrawal, say) is a negative line on the same
invoice; if that leaves the sponsor overpaid, a refund *request* is raised
in ``unified_refunds`` for Finance to approve and pay - nothing is paid
automatically.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.domains.finance.domain.tuition import access
from education_system.systems.university.domains.finance.domain.tuition import sponsors


# ── refund requests ─────────────────────────────────────────────────────


def request_refund(conn, actor, *, amount, reason, source_type, reference_type, reference_id,
                   student_id=None, customer_name=None, customer_email=None) -> int:
    """A ``pending`` refund request in ``unified_refunds`` - the Refunds tab
    and CLI approve and process it. Returns its id."""
    if not access.has_table(conn, "unified_refunds"):
        raise ValueError("Finance's refunds table is missing; open the Finance window once to "
                         "set it up, then retry")
    stamp = access.now()
    new_id = conn.execute(
        "INSERT INTO unified_refunds (source_type, reference_type, reference_id, student_id, "
        "customer_name, customer_email, amount, original_amount, currency, refund_type, "
        "refund_method, refund_reference, reason, status, department, requested_by, "
        "refund_date, request_date, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'GBP', "
        "'withdrawal', 'bank_transfer', ?, ?, 'pending', 'finance', ?, ?, ?, ?, ?)",
        (source_type, reference_type, str(reference_id), student_id, customer_name,
         customer_email, round(float(amount), 2), round(float(amount), 2),
         f"{source_type.upper()}-{reference_id}", reason, str(actor), stamp[:10], stamp[:10],
         "Raised automatically; approve in Refunds before paying", stamp)).lastrowid
    access.audit(conn, actor, "refund.requested", "unified_refund", new_id,
                 student_id=student_id, detail={"amount": amount, "reason": reason,
                                                "source": source_type})
    return int(new_id)


# ── invoices ────────────────────────────────────────────────────────────


def _draft(conn, sponsor_id, year, po_number) -> int:
    row = conn.execute("SELECT invoice_id FROM sponsor_invoices WHERE sponsor_id = ? AND "
                       "academic_year = ? AND status = 'draft' AND po_number IS ? ORDER BY "
                       "invoice_id LIMIT 1", (int(sponsor_id), year, po_number)).fetchone()
    if row:
        return int(row[0])
    return int(conn.execute("INSERT INTO sponsor_invoices (sponsor_id, academic_year, "
                            "po_number) VALUES (?, ?, ?)",
                            (int(sponsor_id), year, po_number)).lastrowid)


def add_line(conn, actor, agreement, student_id, academic_year, amount, description,
             charge_id=None) -> int:
    """The sponsor's share as a line on their draft invoice. Returns the line id."""
    access.ensure(conn)
    year = access.year_label(academic_year)
    invoice_id = _draft(conn, agreement["sponsor_id"], year, agreement.get("po_number"))
    line_id = conn.execute(
        "INSERT INTO sponsor_invoice_lines (invoice_id, student_id, agreement_id, "
        "tuition_charge_id, description, amount) VALUES (?, ?, ?, ?, ?, ?)",
        (invoice_id, str(student_id), agreement["agreement_id"], charge_id, description,
         round(float(amount), 2))).lastrowid
    access.audit(conn, actor, "sponsor_invoice.line_added", "sponsor_invoice", invoice_id,
                 student_id=student_id, detail={"line_id": line_id, "amount": amount,
                                                "description": description})
    return int(line_id)


def totals(conn, invoice_id) -> dict:
    total = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM sponsor_invoice_lines WHERE "
                         "invoice_id = ?", (int(invoice_id),)).fetchone()[0]
    paid = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM sponsor_payment_allocations "
                        "WHERE invoice_id = ?", (int(invoice_id),)).fetchone()[0]
    total, paid = round(float(total or 0), 2), round(float(paid or 0), 2)
    return {"total": total, "paid": paid, "balance": round(total - paid, 2)}


def invoices(conn, *, sponsor_id=None, status=None) -> list[dict]:
    access.ensure(conn)
    sql = ("SELECT i.*, s.name AS sponsor FROM sponsor_invoices i JOIN sponsors s ON "
           "s.sponsor_id = i.sponsor_id WHERE 1 = 1")
    params: list = []
    if sponsor_id is not None:
        sql += " AND i.sponsor_id = ?"
        params.append(int(sponsor_id))
    if status:
        sql += " AND i.status = ?"
        params.append(status)
    rows = access.dicts(conn.execute(sql + " ORDER BY i.invoice_id DESC", params))
    for r in rows:
        r.update(totals(conn, r["invoice_id"]))
    return rows


def invoice(conn, invoice_id) -> dict:
    access.ensure(conn)
    row = access.one(conn.execute(
        "SELECT i.*, s.name AS sponsor, s.contact_name, s.contact_email, s.billing_address, "
        "s.vat_number, s.payment_terms_days FROM sponsor_invoices i JOIN sponsors s ON "
        "s.sponsor_id = i.sponsor_id WHERE i.invoice_id = ?", (int(invoice_id),)))
    if not row:
        raise ValueError(f"No sponsor invoice {invoice_id}")
    row["lines"] = access.dicts(conn.execute(
        "SELECT l.*, TRIM(COALESCE(st.first_name, '') || ' ' || COALESCE(st.last_name, '')) "
        "AS student_name FROM sponsor_invoice_lines l LEFT JOIN students st ON st.student_id = "
        "l.student_id WHERE l.invoice_id = ? ORDER BY l.line_id", (int(invoice_id),)))
    row["allocations"] = access.dicts(conn.execute(
        "SELECT a.*, p.received_on, p.reference FROM sponsor_payment_allocations a JOIN "
        "sponsor_payments p ON p.payment_id = a.payment_id WHERE a.invoice_id = ? ORDER BY "
        "a.allocation_id", (int(invoice_id),)))
    row.update(totals(conn, invoice_id))
    return row


def issue(conn, who, invoice_id, due_date=None) -> dict:
    access.ensure(conn)
    access.require(conn, who, access.SPONSORS)
    row = invoice(conn, invoice_id)
    if row["status"] != "draft":
        raise ValueError(f"Invoice {row['invoice_number'] or invoice_id} is {row['status']}")
    if row["total"] <= 0:
        raise ValueError("The invoice has nothing to bill")
    due = due_date or (date.today() + timedelta(days=int(row["payment_terms_days"] or 30))
                       ).isoformat()
    number = f"SPN-{access.year_start(row['academic_year'])}-{int(invoice_id):05d}"
    conn.execute("UPDATE sponsor_invoices SET status = 'issued', invoice_number = ?, "
                 "issued_at = ?, issued_by = ?, due_date = ? WHERE invoice_id = ?",
                 (number, access.now(), who.username, due, int(invoice_id)))
    access.audit(conn, who.username, "sponsor_invoice.issued", "sponsor_invoice", invoice_id,
                 detail={"number": number, "total": row["total"], "due": due})
    return {"invoice_number": number, "due_date": due, "total": row["total"]}


def cancel_invoice(conn, who, invoice_id, reason) -> None:
    access.ensure(conn)
    access.require(conn, who, access.SPONSORS)
    reason = access.text(reason, "Reason", True)
    row = invoice(conn, invoice_id)
    if row["status"] in ("cancelled", "paid") or row["paid"]:
        raise ValueError("Only an unpaid draft or issued invoice can be cancelled")
    conn.execute("UPDATE sponsor_invoices SET status = 'cancelled' WHERE invoice_id = ?",
                 (int(invoice_id),))
    access.audit(conn, who.username, "sponsor_invoice.cancelled", "sponsor_invoice", invoice_id,
                 detail={"reason": reason, "total": row["total"]})


def _settle(conn, invoice_id) -> None:
    row = conn.execute("SELECT status FROM sponsor_invoices WHERE invoice_id = ?",
                       (int(invoice_id),)).fetchone()
    balance = totals(conn, invoice_id)["balance"]
    if row and row[0] == "issued" and balance <= 0:
        conn.execute("UPDATE sponsor_invoices SET status = 'paid' WHERE invoice_id = ?",
                     (int(invoice_id),))
    elif row and row[0] == "paid" and balance > 0:
        conn.execute("UPDATE sponsor_invoices SET status = 'issued' WHERE invoice_id = ?",
                     (int(invoice_id),))


def credit_line(conn, actor, line_id, amount, description) -> tuple[int | None, int | None]:
    """Credit ``amount`` against the invoice an earlier line is on. Returns
    ``(credit line id, sponsor refund request id)``; a refund is requested
    only when the sponsor has now paid more than the invoice is worth."""
    access.ensure(conn)
    amount = round(float(amount), 2)
    line = access.one(conn.execute(
        "SELECT l.*, i.status, i.sponsor_id FROM sponsor_invoice_lines l JOIN sponsor_invoices "
        "i ON i.invoice_id = l.invoice_id WHERE l.line_id = ?", (int(line_id),)))
    if not line or amount <= 0 or line["status"] == "cancelled":
        return None, None
    new_line = conn.execute(
        "INSERT INTO sponsor_invoice_lines (invoice_id, student_id, agreement_id, "
        "tuition_charge_id, description, amount) VALUES (?, ?, ?, ?, ?, ?)",
        (line["invoice_id"], line["student_id"], line["agreement_id"],
         line["tuition_charge_id"], description, -amount)).lastrowid
    access.audit(conn, actor, "sponsor_invoice.credited", "sponsor_invoice", line["invoice_id"],
                 student_id=line["student_id"], detail={"amount": amount,
                                                        "description": description})
    over = -totals(conn, line["invoice_id"])["balance"]
    refund_id = None
    if over > 0:
        sponsor = sponsors.get_sponsor(conn, line["sponsor_id"])
        refund_id = request_refund(
            conn, actor, amount=over, reason=f"Sponsor overpaid after credit: {description}",
            source_type="sponsor", reference_type="sponsor_invoice",
            reference_id=line["invoice_id"], customer_name=sponsor["name"],
            customer_email=sponsor.get("contact_email"))
    _settle(conn, line["invoice_id"])
    return int(new_line), refund_id


# ── payments ────────────────────────────────────────────────────────────


def record_payment(conn, who, sponsor_id, amount, received_on, *, method=None,
                   reference=None, allocate=True) -> dict:
    """Record money received from a sponsor and (by default) allocate it to
    their oldest issued invoices. Returns the payment id and allocations."""
    access.ensure(conn)
    access.require(conn, who, access.SPONSORS)
    sponsors.get_sponsor(conn, sponsor_id)
    amount = access.money(amount, "Amount", allow_zero=False)
    try:
        received = date.fromisoformat(str(received_on or access.today())[:10]).isoformat()
    except ValueError:
        raise ValueError("The date received is YYYY-MM-DD") from None
    payment_id = int(conn.execute(
        "INSERT INTO sponsor_payments (sponsor_id, amount, received_on, method, reference, "
        "recorded_by) VALUES (?, ?, ?, ?, ?, ?)",
        (int(sponsor_id), amount, received, access.text(method, "Method"),
         access.text(reference, "Reference"), who.username)).lastrowid)
    access.audit(conn, who.username, "sponsor_payment.recorded", "sponsor_payment", payment_id,
                 detail={"sponsor_id": sponsor_id, "amount": amount, "reference": reference})
    done = auto_allocate(conn, who, payment_id) if allocate else []
    return {"payment_id": payment_id, "allocations": done,
            "unallocated": unallocated(conn, payment_id)}


def unallocated(conn, payment_id) -> float:
    row = conn.execute("SELECT p.amount - COALESCE((SELECT SUM(a.amount) FROM "
                       "sponsor_payment_allocations a WHERE a.payment_id = p.payment_id), 0) "
                       "FROM sponsor_payments p WHERE p.payment_id = ?",
                       (int(payment_id),)).fetchone()
    if not row:
        raise ValueError(f"No sponsor payment {payment_id}")
    return round(float(row[0] or 0), 2)


def allocate(conn, who, payment_id, invoice_id, amount) -> int:
    access.ensure(conn)
    access.require(conn, who, access.SPONSORS)
    amount = access.money(amount, "Amount", allow_zero=False)
    pay = conn.execute("SELECT sponsor_id FROM sponsor_payments WHERE payment_id = ?",
                       (int(payment_id),)).fetchone()
    inv = invoice(conn, invoice_id)
    if not pay or int(pay[0]) != int(inv["sponsor_id"]):
        raise ValueError("The payment and invoice belong to different sponsors")
    if inv["status"] != "issued":
        raise ValueError("Allocate only to an issued, unpaid invoice")
    if amount > unallocated(conn, payment_id) + 0.005:
        raise ValueError(f"Only £{unallocated(conn, payment_id):,.2f} of the payment is left")
    if amount > inv["balance"] + 0.005:
        raise ValueError(f"The invoice only has £{inv['balance']:,.2f} outstanding")
    new_id = conn.execute("INSERT INTO sponsor_payment_allocations (payment_id, invoice_id, "
                          "amount, allocated_by) VALUES (?, ?, ?, ?)",
                          (int(payment_id), int(invoice_id), amount, who.username)).lastrowid
    _settle(conn, invoice_id)
    access.audit(conn, who.username, "sponsor_payment.allocated", "sponsor_invoice", invoice_id,
                 detail={"payment_id": payment_id, "amount": amount})
    return int(new_id)


def auto_allocate(conn, who, payment_id) -> list[dict]:
    pay = conn.execute("SELECT sponsor_id FROM sponsor_payments WHERE payment_id = ?",
                       (int(payment_id),)).fetchone()
    if not pay:
        raise ValueError(f"No sponsor payment {payment_id}")
    done = []
    for inv in reversed(invoices(conn, sponsor_id=pay[0], status="issued")):
        left = unallocated(conn, payment_id)
        if left <= 0:
            break
        part = round(min(left, inv["balance"]), 2)
        if part > 0:
            allocate(conn, who, payment_id, inv["invoice_id"], part)
            done.append({"invoice_id": inv["invoice_id"],
                         "invoice_number": inv["invoice_number"], "amount": part})
    return done


def payments(conn, sponsor_id=None) -> list[dict]:
    access.ensure(conn)
    sql = ("SELECT p.*, s.name AS sponsor FROM sponsor_payments p JOIN sponsors s ON "
           "s.sponsor_id = p.sponsor_id")
    params: list = []
    if sponsor_id is not None:
        sql += " WHERE p.sponsor_id = ?"
        params.append(int(sponsor_id))
    rows = access.dicts(conn.execute(sql + " ORDER BY p.payment_id DESC", params))
    for r in rows:
        r["unallocated"] = unallocated(conn, r["payment_id"])
    return rows


# ── PDFs ────────────────────────────────────────────────────────────────


def _generator(path):
    from education_system.systems.university.services.pdf_export.pdf_generator import (
        PDFGenerator,
    )
    return PDFGenerator(str(path))


def write_invoice_pdf(conn, invoice_id, path) -> str:
    """The invoice as a PDF at ``path`` (through the shared PDF generator)."""
    inv = invoice(conn, invoice_id)
    pdf = _generator(path)
    title = f"Invoice {inv['invoice_number'] or '(draft - not yet issued)'}"
    pdf.add_section_header(title)
    for label, value in (("To", inv["sponsor"]), ("Attention", inv.get("contact_name")),
                         ("Billing address", inv.get("billing_address")),
                         ("VAT number", inv.get("vat_number")),
                         ("Purchase order", inv.get("po_number")),
                         ("Academic year", inv["academic_year"]),
                         ("Issued", str(inv.get("issued_at") or "")[:10] or "not issued"),
                         ("Due", inv.get("due_date") or "-")):
        if value:
            pdf.add_text(f"<b>{label}:</b> {value}")
    pdf.add_spacer()
    pdf.add_data_table(["Student", "Name", "Description", "Amount (GBP)"],
                       [(ln["student_id"], ln["student_name"], ln["description"],
                         f"{ln['amount']:,.2f}") for ln in inv["lines"]],
                       max_rows=500, max_col_width=2.6)
    pdf.add_text(f"<b>Total:</b> £{inv['total']:,.2f} &nbsp; <b>Paid:</b> £{inv['paid']:,.2f}"
                 f" &nbsp; <b>Balance due:</b> £{inv['balance']:,.2f}")
    if not pdf.save():
        raise ValueError("The PDF could not be written (see the log)")
    return str(path)


def write_letter_pdf(conn, agreement_id, path, *, signatory="Student Finance") -> str:
    """A sponsor letter confirming the sponsorship of one student, as a PDF."""
    ag = sponsors.get_agreement(conn, agreement_id)
    sp = sponsors.get_sponsor(conn, ag["sponsor_id"])
    st = access.student_row(conn, ag["student_id"])
    share = (f"{ag['value']:g}% of tuition" if ag["basis"] == "percent"
             else f"£{ag['value']:,.2f} a year")
    years = f"{access.year_label(ag['start_year'])} to {access.year_label(ag['end_year'])}"
    pdf = _generator(path)
    pdf.add_text(access.today())
    pdf.add_spacer()
    for line in (sp.get("contact_name"), sp["name"], sp.get("billing_address")):
        if line:
            pdf.add_text(str(line).replace("\n", "<br/>"))
    pdf.add_spacer()
    pdf.add_section_header("Confirmation of sponsorship")
    pdf.add_text(
        f"We confirm that {sp['name']} sponsors {st['name']} (student number "
        f"{st['student_id']}) on {st.get('course') or 'their programme'} for {years}, "
        f"covering {share}" + (f", up to £{ag['cap_amount']:,.2f} in total"
                               if ag.get("cap_amount") else "") + ".")
    billed = sponsors.billed_to_date(conn, ag["agreement_id"])
    pdf.add_text(f"Invoiced to date under this agreement: £{billed:,.2f}."
                 +(f" Purchase order {ag['po_number']}." if ag.get("po_number") else ""))
    pdf.add_text("The sponsor's share of each year's tuition is invoiced to the sponsor; the "
                 "student is charged the remainder. Please contact Student Finance with any "
                 "change to the sponsorship.")
    pdf.add_spacer()
    pdf.add_text(f"Yours faithfully,<br/><br/>{signatory}")
    if not pdf.save():
        raise ValueError("The PDF could not be written (see the log)")
    return str(path)
