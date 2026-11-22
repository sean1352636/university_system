"""Invoices and payments.

Rules:

* an invoice bills either a client or a learner (self-funded), not both;
  numbers ``INV-<year>-0001`` are given automatically;
* VAT and the total are worked out from the net amount; the due date
  follows the client's credit terms (14 days for a learner);
* sending an invoice that takes a client over their credit limit (with what
  they already owe) is refused;
* an invoice with payments can't be cancelled; cancelling one frees its
  bookings to be invoiced again;
* a payment is above zero, no more than what's outstanding, and only
  against a sent invoice. What's paid and the payment state (Unpaid / Part
  paid / Paid / Overdue) are always worked out from the payments.

``raise_invoice`` gathers a payer's uninvoiced, chargeable bookings into one
draft invoice.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.training_provider.infrastructure import database as db
from education_system.systems.training_provider.modules import clients, learners, sessions

STATUSES = ("Draft", "Sent", "Cancelled")
METHODS = ("BACS", "Card", "Cheque", "Cash", "Direct debit", "Grant / funding body")
LEARNER_TERMS = 14
VAT_RATE = 20.0


def paid(invoice_id: int, conn=None) -> float:
    sql = "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = ?"
    if conn is not None:
        return float(conn.execute(sql, (invoice_id,)).fetchone()[0])
    with db.connect() as c:
        return float(c.execute(sql, (invoice_id,)).fetchone()[0])


def outstanding(row: dict) -> float:
    if row.get("status") != "Sent":
        return 0.0
    return round(float(row.get("total") or 0) - paid(row["id"]), 2)


def payment_state(row: dict) -> str:
    if row.get("status") != "Sent":
        return row.get("status") or ""
    owed = outstanding(row)
    if owed <= 0:
        return "Paid"
    due = r.to_date(row.get("due_on"))
    late = " - OVERDUE" if due and due < date.today() else ""
    return ("Part paid" if owed < float(row.get("total") or 0) else "Unpaid") + late


def client_owes(client_id: int, *, excluding: int | None = None) -> float:
    return round(sum(outstanding(i) for i in
                     r.list_records(INVOICES, equals={"client_id": client_id})
                     if i["id"] != excluding), 2)


def _check_invoice(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if bool(merged.get("client_id")) == bool(merged.get("learner_id")):
        raise ValidationError("Bill either a client or a learner (one, not both).")
    status, was = merged.get("status"), (old or {}).get("status")
    if was == "Cancelled" and status != "Cancelled":
        raise ValidationError("A cancelled invoice stays cancelled: raise a new one.")
    if old is not None and was == "Sent" and any(
            k in values and values[k] != old.get(k) for k in
            ("net", "vat_rate", "client_id", "learner_id")):
        raise ValidationError("A sent invoice can't be changed: cancel it and raise another "
                              "(or record a credit).")
    net = float(merged.get("net") or 0)
    if net <= 0:
        raise ValidationError("The net amount must be above zero.")
    rate = float(merged.get("vat_rate") if merged.get("vat_rate") is not None else VAT_RATE)
    if not 0 <= rate <= 100:
        raise ValidationError("The VAT rate is 0-100%.")
    values["vat_rate"] = rate
    values["vat"] = round(net * rate / 100, 2)
    values["total"] = round(net + values["vat"], 2)
    issued = r.to_date(merged.get("issued_on")) or date.today()
    values["issued_on"] = issued.isoformat()
    client = r.get(clients.CLIENTS, int(merged["client_id"])) if merged.get("client_id") \
        else None
    if merged.get("due_on") in (None, "") or "issued_on" in values and old and \
            values["issued_on"] != old.get("issued_on"):
        terms = int(client.get("credit_days") or 0) if client else LEARNER_TERMS
        values["due_on"] = (issued + timedelta(days=terms)).isoformat()
    if client is not None and client.get("po_required") and not merged.get("po_number"):
        raise ValidationError(f"{client['name']} needs a purchase order number on invoices.")
    if status == "Sent" and was != "Sent" and client is not None and \
            client.get("credit_limit") is not None:
        owes = client_owes(client["id"], excluding=(old or {}).get("id"))
        if owes + values["total"] > float(client["credit_limit"]):
            raise ValidationError(
                f"{client['name']} already owes £{owes:,.2f}; this would take them over their "
                f"£{float(client['credit_limit']):,.2f} credit limit.")
    if status == "Cancelled" and old is not None and paid(old["id"]) > 0:
        raise ValidationError("Payments have been taken against this invoice, so it can't be "
                              "cancelled.")
    if old is None:
        with db.connect() as conn:
            n = conn.execute("SELECT COUNT(*) + 1 FROM invoices WHERE invoice_no LIKE ?",
                             (f"INV-{issued.year}-%",)).fetchone()[0]
            while conn.execute("SELECT 1 FROM invoices WHERE invoice_no = ?",
                               (f"INV-{issued.year}-{n:04d}",)).fetchone():
                n += 1
        values["invoice_no"] = f"INV-{issued.year}-{n:04d}"


def _after_invoice(conn, row: dict, old: dict | None) -> None:
    if row["status"] == "Cancelled" and (old or {}).get("status") != "Cancelled":
        conn.execute("UPDATE bookings SET invoice_id = NULL WHERE invoice_id = ?", (row["id"],))


def payer(row: dict) -> str:
    if row.get("client_id"):
        c = r.get(clients.CLIENTS, row["client_id"])
        return c["name"] if c else "?"
    return row.get("learner_name") or ""


INVOICES = RecordType(
    key="invoices", title="Invoices", singular="invoice",
    order_by="issued_on DESC, id DESC", check=_check_invoice, after_save=_after_invoice,
    filters=("status",), describe=lambda row: row.get("invoice_no") or "invoice",
    computed=(("Bill to", payer),
              ("Outstanding", lambda row: f"£{outstanding(row):,.2f}"),
              ("Payment", payment_state)),
    fields=(
        Field("invoice_no", "Invoice", form=False),
        Field("client_id", "Client", "ref", ref="clients"),
        Field("learner_id", "Learner (self-funded)", "learner"),
        Field("issued_on", "Issued", "date"),
        Field("due_on", "Due", "date", help="Blank: from the credit terms"),
        Field("po_number", "PO number", listed=False),
        Field("description", "Description", "long", listed=False),
        Field("net", "Net", "money", required=True),
        Field("vat_rate", "VAT %", "number", default=VAT_RATE, listed=False),
        Field("vat", "VAT", "money", form=False, listed=False),
        Field("total", "Total", "money", form=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="Draft"),
    ),
)


def _check_payment(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    inv = r.get(INVOICES, int(merged["invoice_id"])) if merged.get("invoice_id") else None
    if inv is None:
        raise ValidationError("Choose the invoice.")
    if inv["status"] != "Sent":
        raise ValidationError(f"{inv['invoice_no']} is {inv['status'].lower()}: payments go "
                              "against sent invoices.")
    amount = float(merged.get("amount") or 0)
    if amount <= 0:
        raise ValidationError("The amount must be above zero.")
    owed = outstanding(inv) + float((old or {}).get("amount") or 0)
    if amount > owed + 0.005:
        raise ValidationError(f"Only £{owed:,.2f} is outstanding on {inv['invoice_no']}.")
    on = r.to_date(merged.get("paid_on"))
    if on and on > date.today():
        raise ValidationError("A payment can't be dated in the future.")


PAYMENTS = RecordType(
    key="payments", title="Payments", singular="payment", order_by="paid_on DESC, id DESC",
    check=_check_payment, filters=("method",),
    describe=lambda row: f"Payment £{float(row.get('amount') or 0):,.2f}",
    computed=(("Invoice", lambda row: (r.get(INVOICES, row["invoice_id"]) or {})
               .get("invoice_no", "")),),
    fields=(
        Field("invoice_id", "Invoice", "ref", ref="invoices", required=True),
        Field("paid_on", "Paid", "date", required=True),
        Field("amount", "Amount", "money", required=True),
        Field("method", "Method", "choice", METHODS, required=True, default="BACS"),
        Field("reference", "Reference"),
    ),
)


def uninvoiced(*, client_id: int | None = None, learner_id: int | None = None) -> list[dict]:
    """Chargeable bookings with no invoice for one payer (or all payers)."""
    out = []
    for b in r.list_records(sessions.BOOKINGS):
        if b.get("invoice_id") or sessions.chargeable(b) <= 0:
            continue
        if client_id is not None and b.get("client_id") != client_id:
            continue
        if learner_id is not None and (b.get("client_id") or b["learner_id"] != learner_id):
            continue
        out.append(b)
    return out


def payers_to_invoice() -> list[tuple[str, int, str, float]]:
    """``(kind, id, name, amount)`` for each payer with uninvoiced charges."""
    totals: dict[tuple[str, int], float] = {}
    for b in uninvoiced():
        key = ("client", b["client_id"]) if b.get("client_id") else ("learner", b["learner_id"])
        totals[key] = totals.get(key, 0.0) + sessions.chargeable(b)
    out = []
    for (kind, pid), amount in totals.items():
        if kind == "client":
            row = r.get(clients.CLIENTS, pid)
            name = row["name"] if row else "?"
        else:
            row = r.get(learners.LEARNERS, pid)
            name = learners.learner_label(row) if row else "?"
        out.append((kind, pid, name, round(amount, 2)))
    return sorted(out, key=lambda x: x[2].lower())


def raise_invoice(*, client_id: int | None = None, learner_id: int | None = None,
                  po_number: str | None = None, actor: str = "system") -> int:
    """Gather the payer's uninvoiced charges into a Draft invoice; returns its id."""
    if bool(client_id) == bool(learner_id):
        raise ValidationError("Choose a client or a learner to invoice.")
    rows = uninvoiced(client_id=client_id, learner_id=learner_id)
    if not rows:
        raise ValidationError("Nothing to invoice for them.")
    lines = []
    for b in rows:
        s = r.get(sessions.SESSIONS, b["session_id"])
        what = "cancellation charge" if b["status"] == "Cancelled" else "place"
        lines.append(f"{b['learner_name']} - {sessions.session_label(s)} {what}: "
                     f"£{sessions.chargeable(b):,.2f}")
    po = po_number or next((b["po_number"] for b in rows if b.get("po_number")), None)
    inv_id = r.save(INVOICES, {"client_id": client_id, "learner_id": learner_id,
                               "net": round(sum(sessions.chargeable(b) for b in rows), 2),
                               "po_number": po, "description": "\n".join(lines),
                               "status": "Draft"}, actor=actor)
    with db.connect() as conn:
        conn.executemany("UPDATE bookings SET invoice_id = ? WHERE id = ?",
                         [(inv_id, b["id"]) for b in rows])
    return inv_id


def aged_debt() -> dict[str, float]:
    bands = {"Not yet due": 0.0, "1-30 days": 0.0, "31-60 days": 0.0, "61-90 days": 0.0,
             "Over 90 days": 0.0}
    for inv in r.list_records(INVOICES, equals={"status": "Sent"}):
        owed = outstanding(inv)
        if owed <= 0:
            continue
        late = (date.today() - (r.to_date(inv["due_on"]) or date.today())).days
        key = ("Not yet due" if late <= 0 else "1-30 days" if late <= 30 else
               "31-60 days" if late <= 60 else "61-90 days" if late <= 90 else "Over 90 days")
        bands[key] += owed
    return {k: round(v, 2) for k, v in bands.items()}


def overdue_invoices() -> list[dict]:
    return [i for i in r.list_records(INVOICES, equals={"status": "Sent"})
            if outstanding(i) > 0 and (r.to_date(i["due_on"]) or date.today()) < date.today()]

