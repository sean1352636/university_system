"""Invoicing, payments, reports and the menu catalogue."""

from __future__ import annotations

from datetime import date

import pytest

from education_system.systems.training_provider.app import routing
from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.modules import clients, finance, reports, sessions
from education_system.systems.training_provider.ui.gui import pages


@pytest.fixture
def booked(world, make_learner):
    """An employer-funded booking (£270 after discount) and a self-funded one (£300)."""
    emp = make_learner("A", "X", funding="Employer", client_id=world.client)
    own = make_learner("B", "X")
    be = r.save(sessions.BOOKINGS, {"learner_id": emp, "session_id": world.session,
                                    "po_number": "PO1"})
    bo = r.save(sessions.BOOKINGS, {"learner_id": own, "session_id": world.session})
    return emp, own, be, bo


def test_payers_and_raising_an_invoice(world, booked):
    emp, own, be, _bo = booked
    payers = {(k, pid): amt for k, pid, _n, amt in finance.payers_to_invoice()}
    assert payers == {("client", world.client): 270.0, ("learner", own): 300.0}
    inv = r.get(finance.INVOICES, finance.raise_invoice(client_id=world.client))
    assert inv["invoice_no"] == f"INV-{date.today().year}-0001"
    assert (inv["net"], inv["vat"], inv["total"]) == (270.0, 54.0, 324.0)
    assert inv["po_number"] == "PO1" and inv["status"] == "Draft"
    assert r.get(sessions.BOOKINGS, be)["invoice_id"] == inv["id"]
    with pytest.raises(r.ValidationError, match="Nothing to invoice"):
        finance.raise_invoice(client_id=world.client)
    with pytest.raises(r.ValidationError, match="invoiced"):
        r.save(sessions.BOOKINGS, {"price": 1}, record_id=be)


def test_bill_one_payer_only(world, make_learner):
    with pytest.raises(r.ValidationError, match="one, not both"):
        r.save(finance.INVOICES, {"client_id": world.client, "learner_id": make_learner(),
                                  "net": 10, "po_number": "P"})


def test_payments_and_state(world, booked):
    inv = finance.raise_invoice(client_id=world.client)
    with pytest.raises(r.ValidationError, match="sent invoices"):
        r.save(finance.PAYMENTS, {"invoice_id": inv, "paid_on": date.today().isoformat(),
                                  "amount": 10})
    r.save(finance.INVOICES, {"status": "Sent"}, record_id=inv)
    with pytest.raises(r.ValidationError, match="can't be changed"):
        r.save(finance.INVOICES, {"net": 5}, record_id=inv)
    with pytest.raises(r.ValidationError, match="outstanding"):
        r.save(finance.PAYMENTS, {"invoice_id": inv, "paid_on": date.today().isoformat(),
                                  "amount": 1000})
    r.save(finance.PAYMENTS, {"invoice_id": inv, "paid_on": date.today().isoformat(),
                              "amount": 100})
    row = r.get(finance.INVOICES, inv)
    assert finance.outstanding(row) == 224.0
    assert finance.payment_state(row) == "Part paid"
    with pytest.raises(r.ValidationError, match="can't be\\s+cancelled"):
        r.save(finance.INVOICES, {"status": "Cancelled"}, record_id=inv)


def test_cancelling_an_invoice_frees_its_bookings(world, booked):
    inv = finance.raise_invoice(client_id=world.client)
    r.save(finance.INVOICES, {"status": "Cancelled"}, record_id=inv)
    assert r.get(sessions.BOOKINGS, booked[2])["invoice_id"] is None


def test_credit_limit_on_sending(world, make_learner):
    r.save(clients.CLIENTS, {"credit_limit": 100}, record_id=world.client)
    inv = r.save(finance.INVOICES, {"client_id": world.client, "net": 200, "po_number": "P"})
    with pytest.raises(r.ValidationError, match="credit limit"):
        r.save(finance.INVOICES, {"status": "Sent"}, record_id=inv)


def test_dashboard_and_reports_run(world, booked):
    d = reports.dashboard()
    assert d["learners"] == 2 and d["uninvoiced"] == 570.0
    assert isinstance(reports.due_items(), list)
    reports.session_fill()
    reports.achievement()
    reports.booking_summary()
    reports.revenue_by_month()
    reports.quality_summary()


def test_export_csv(world, booked, tmp_path):
    path = tmp_path / "b.csv"
    assert reports.export_csv(sessions.BOOKINGS, path) == 2
    assert path.read_text(encoding="utf-8").startswith("Learner,")


def test_every_menu_key_is_a_record_type_or_handled():
    from education_system.systems.training_provider.app import cli_main, gui_main
    for _label, key in routing.all_entries():
        assert (key in r.REGISTRY or key in pages.CUSTOM
                or hasattr(gui_main.TPMainGUI, f"open_{key}")), key
        assert key in r.REGISTRY or hasattr(cli_main.TPCLI, f"do_{key}"), key
    for _label, key in routing.PROFILE_TABS:
        assert r.REGISTRY[key].learner_field is not None
