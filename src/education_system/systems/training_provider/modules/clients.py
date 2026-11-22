"""Employer clients and their training contracts.

Rules:

* each client gets an account number ``CL`` + four digits; names are unique;
* credit terms are 0-90 days; a client On hold or Closed can't take new
  bookings (checked on the booking);
* a contract ends after it starts; an Active contract must be in date;
  contracts expiring in the next 60 days show on Due & Overdue.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.training_provider.infrastructure import database as db
from education_system.systems.training_provider.modules import learners

KINDS = ("Private company", "Public sector", "Charity / voluntary", "School / college",
         "NHS / care provider", "Other")
STATUSES = ("Active", "On hold", "Closed")
CONTRACT_STATUSES = ("Draft", "Active", "Expired", "Cancelled")


def _check_client(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    learners.check_email(values, "contact_email")
    learners.check_email(values, "billing_email")
    learners.check_phone(values, "contact_phone")
    learners.check_postcode(values)
    terms = merged.get("credit_days")
    if terms is not None and not 0 <= int(terms) <= 90:
        raise ValidationError("Credit terms are between 0 and 90 days.")
    if merged.get("status") == "On hold" and not merged.get("hold_reason"):
        raise ValidationError("Give the reason the account is on hold.")
    if old is None:
        with db.connect() as conn:
            n = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM clients").fetchone()[0]
        values["account_no"] = f"CL{n:04d}"


CLIENTS = RecordType(
    key="clients", title="Clients", singular="client", order_by="name",
    check=_check_client, filters=("kind", "status"),
    describe=lambda row: row.get("name") or "client",
    fields=(
        Field("account_no", "Account", form=False),
        Field("name", "Organisation", required=True),
        Field("kind", "Type", "choice", KINDS, required=True, default=KINDS[0]),
        Field("contact_name", "Contact"),
        Field("contact_email", "Contact e-mail", listed=False),
        Field("contact_phone", "Contact phone"),
        Field("billing_email", "Invoices to (e-mail)", listed=False),
        Field("address_line1", "Address", listed=False),
        Field("postcode", "Postcode", listed=False),
        Field("credit_days", "Credit terms (days)", "int", default=30, listed=False),
        Field("credit_limit", "Credit limit", "money", listed=False,
              help="Blank: no limit"),
        Field("po_required", "Purchase order needed", "bool", default=0, listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="Active"),
        Field("hold_reason", "Hold reason", listed=False),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def _check_contract(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    start, end = r.to_date(merged.get("start_date")), r.to_date(merged.get("end_date"))
    if start and end and end <= start:
        raise ValidationError("A contract ends after it starts.")
    if merged.get("status") == "Active" and end and end < date.today():
        raise ValidationError("That contract has ended: mark it Expired.")


def _expires(row: dict) -> str:
    end = r.to_date(row.get("end_date"))
    if not end or row.get("status") != "Active":
        return ""
    days = (end - date.today()).days
    return f"{days} days" if days >= 0 else "ENDED"


CONTRACTS = RecordType(
    key="contracts", title="Contracts", singular="contract",
    order_by="end_date DESC, id DESC", check=_check_contract, filters=("status",),
    describe=lambda row: row.get("title") or "contract",
    computed=(("Ends in", _expires),),
    fields=(
        Field("client_id", "Client", "ref", ref="clients", required=True, on_delete="CASCADE"),
        Field("title", "Title", required=True),
        Field("start_date", "Starts", "date", required=True),
        Field("end_date", "Ends", "date", required=True),
        Field("value", "Value", "money"),
        Field("discount_pct", "Discount on list price %", "number", listed=False),
        Field("terms", "Service levels / terms", "long", listed=False),
        Field("status", "Status", "choice", CONTRACT_STATUSES, required=True, default="Draft"),
    ),
)


def contract_discount(client_id: int | None, on: date) -> float:
    """The discount % of the client's active contract covering *on* (0 if none)."""
    if not client_id:
        return 0.0
    for c in r.list_records(CONTRACTS, equals={"client_id": client_id, "status": "Active"}):
        start, end = r.to_date(c["start_date"]), r.to_date(c["end_date"])
        if start and end and start <= on <= end:
            return float(c.get("discount_pct") or 0)
    return 0.0
