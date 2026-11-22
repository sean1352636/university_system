"""Commissioning: invoicing a placement's commissioner (home school or LA).

Rules:

* an invoice is for one placement and a period inside the placement's dates;
  invoices for the same placement can't overlap (cancelled ones aside);
* left blank, the days are the weekdays in the period scaled by the
  placement's days a week, the rate is the placement's daily rate, and the
  amount is days x rate;
* Sent needs a sent date, Paid a paid date (not before it was sent).
"""

from __future__ import annotations

from datetime import date

from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.alternative_provision.infrastructure import database as db
from education_system.systems.alternative_provision.modules import placements

STATUSES = ("Draft", "Sent", "Paid", "Disputed", "Cancelled")


def _today() -> str:
    return date.today().isoformat()


def _check_invoice(values: dict, old: dict | None) -> None:
    pid = values.get("placement_id") or (old or {}).get("placement_id")
    placement = r.get(placements.PLACEMENTS, int(pid)) if pid else None
    if placement is None:
        raise ValidationError("Choose the placement.")
    values["learner_id"] = placement["learner_id"]
    merged = {**(old or {}), **values}
    start, end = r.to_date(merged.get("period_from")), r.to_date(merged.get("period_to"))
    if not (start and end) or end < start:
        raise ValidationError("The period needs a start and an end, in that order.")
    p_start, p_end = r.to_date(placement["start_date"]), r.to_date(placement.get("end_date"))
    if start < p_start or (p_end and end > p_end):
        raise ValidationError("The period has to be inside the placement's dates.")
    if merged.get("status") != "Cancelled":
        with db.connect() as conn:
            clash = conn.execute(
                "SELECT invoice_no FROM invoices WHERE placement_id = ? AND status != "
                "'Cancelled' AND period_from <= ? AND period_to >= ? AND id IS NOT ?",
                (pid, end.isoformat(), start.isoformat(), (old or {}).get("id"))).fetchone()
        if clash:
            raise ValidationError(f"That period overlaps invoice {clash[0] or 'already raised'}.")
    if merged.get("days") in (None, ""):
        values["days"] = placements.days_in(placement, start, end)
    if merged.get("daily_rate") in (None, ""):
        if not placement.get("daily_rate"):
            raise ValidationError("The placement has no daily rate: enter one here or on the "
                                  "placement.")
        values["daily_rate"] = placement["daily_rate"]
    days = float(values.get("days", merged.get("days")) or 0)
    rate = float(values.get("daily_rate", merged.get("daily_rate")) or 0)
    if merged.get("amount") in (None, ""):
        values["amount"] = round(days * rate, 2)
    if not merged.get("commissioner"):
        values["commissioner"] = placement.get("commissioner") or placement.get("commissioned_by")
    status = merged.get("status")
    sent, paid = r.to_date(merged.get("sent_on")), r.to_date(merged.get("paid_on"))
    if status in ("Sent", "Paid", "Disputed") and not sent:
        values["sent_on"] = _today()
        sent = date.today()
    if status == "Paid" and not paid:
        values["paid_on"] = _today()
        paid = date.today()
    if sent and paid and paid < sent:
        raise ValidationError("An invoice can't be paid before it was sent.")
    if old is None and not merged.get("invoice_no"):
        with db.connect() as conn:
            n = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM invoices").fetchone()[0]
        values["invoice_no"] = f"INV{n:05d}"


INVOICES = RecordType(
    key="invoices", title="Invoices", singular="invoice",
    order_by="period_from DESC, id DESC", check=_check_invoice, filters=("status",),
    describe=lambda row: f"{row.get('invoice_no')} £{row.get('amount') or 0:,.2f}",
    fields=(
        Field("invoice_no", "Invoice", form=False),
        Field("placement_id", "Placement", "ref", ref="placements", required=True),
        Field("learner_id", "Pupil", "learner", form=False),
        Field("commissioner", "Invoice to", help="Left blank: the placement's commissioner"),
        Field("period_from", "From", "date", required=True),
        Field("period_to", "To", "date", required=True),
        Field("days", "Days", "number", help="Left blank: worked out from the placement"),
        Field("daily_rate", "Daily rate", "money", listed=False),
        Field("amount", "Amount", "money", help="Left blank: days x daily rate"),
        Field("status", "Status", "choice", STATUSES, required=True, default="Draft"),
        Field("sent_on", "Sent", "date", listed=False),
        Field("paid_on", "Paid", "date", listed=False),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def outstanding() -> list[dict]:
    return [x for x in r.list_records(INVOICES) if x["status"] in ("Sent", "Disputed")]
