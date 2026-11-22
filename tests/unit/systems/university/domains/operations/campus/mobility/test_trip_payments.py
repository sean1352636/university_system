"""Trip payments: method choice, the funds check, and posting to Finance."""

from __future__ import annotations

import builtins

import pytest

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (  # noqa: E501
    payments,
)


@pytest.fixture()
def answers(monkeypatch):
    """Feed scripted answers to input()."""
    def _drive(*responses):
        it = iter(responses)
        monkeypatch.setattr(builtins, "input", lambda _prompt="": next(it))
    return _drive


class _Finance:
    """Stand-in for finance_bus recording what it was asked to do."""

    def __init__(self, *, balance=None, account_ok=True, payment_id=99,
                 refund_id=7, topup_ok=True):
        self.balance = balance
        self.account_ok = account_ok
        self.payment_id = payment_id
        self.refund_id = refund_id
        self.topup_ok = topup_ok
        self.calls = []

    def record_refund(self, **kwargs):
        self.calls.append(("refund", kwargs))
        return self.refund_id

    def credit_student_account(self, **kwargs):
        self.calls.append(("topup", kwargs))
        if not self.topup_ok:
            return {"success": False, "message": "account closed"}
        self.balance += kwargs["amount"]
        return {"success": True, "new_balance": self.balance}

    def account_balance(self, student_id):
        return self.balance

    def pay_from_student_account(self, **kwargs):
        self.calls.append(("account", kwargs))
        if not self.account_ok:
            return {"success": False, "message": "Insufficient balance. Current: £1.00, Required: £50.00"}
        self.balance -= kwargs["amount"]
        return {
            "success": True,
            "message": "ok",
            "new_balance": self.balance,
            "transaction_id": "Trips_TRIP-1_20260815",
        }

    def record_payment(self, **kwargs):
        self.calls.append(("till", kwargs))
        return self.payment_id


@pytest.fixture()
def finance(monkeypatch):
    def _install(**kwargs):
        stub = _Finance(**kwargs)
        monkeypatch.setattr(payments, "_finance", lambda: stub)
        return stub
    return _install


@pytest.mark.unit
def test_student_account_offered_when_funds_cover_the_cost(answers, capsys):
    answers("3")
    assert payments.select_payment_method(50.0, balance=100.0) == payments.STUDENT_ACCOUNT


@pytest.mark.unit
def test_insufficient_funds_reprompts_for_another_method(answers, capsys):
    answers("3", "2")  # student account (declined), then card

    method = payments.select_payment_method(80.0, balance=50.0)

    assert method == payments.CARD
    out = capsys.readouterr().out
    assert "Insufficient funds" in out
    assert "£50.00" in out and "£80.00" in out


@pytest.mark.unit
def test_student_account_hidden_without_an_account(answers, capsys):
    answers("3", "1")  # 3 is out of range with only cash/card on offer

    method = payments.select_payment_method(20.0, balance=None)

    assert method == payments.CASH
    assert "unavailable" in capsys.readouterr().out


@pytest.mark.unit
def test_blank_choice_cancels(answers):
    answers("")
    assert payments.select_payment_method(20.0, balance=100.0) is None


@pytest.mark.unit
def test_student_account_payment_goes_through_finance(finance):
    stub = finance(balance=100.0)

    result = payments.take_payment(
        method=payments.STUDENT_ACCOUNT, amount=50.0, student_id="S12345",
        trip_id=1, trip_name="Museum Day", processed_by="S12345",
    )

    assert result["success"] is True
    assert result["balance_after"] == 50.0
    assert result["reference"] == "Trips_TRIP-1_20260815"
    kind, kwargs = stub.calls[0]
    assert kind == "account"
    assert kwargs["transaction_source"] == payments.TRANSACTION_SOURCE
    # Finance must re-check the balance itself; the prompt's check is advisory.
    assert kwargs["check_balance"] is True


@pytest.mark.unit
def test_till_payment_is_recorded_against_the_trip(finance):
    stub = finance(balance=None)

    result = payments.take_payment(
        method=payments.CASH, amount=12.5, student_id="S12345",
        trip_id=7, trip_name="Museum Day",
    )

    assert result["success"] is True
    assert result["payment_id"] == 99
    kind, kwargs = stub.calls[0]
    assert kind == "till"
    assert kwargs["payment_method"] == "Cash"
    assert kwargs["transaction_ref"] == "TRIP-7"


@pytest.mark.unit
def test_finance_rejection_comes_back_as_a_message_not_an_exception(finance):
    finance(balance=1.0, account_ok=False)

    result = payments.take_payment(
        method=payments.STUDENT_ACCOUNT, amount=50.0, student_id="S12345",
        trip_id=1, trip_name="Museum Day",
    )

    assert result["success"] is False
    assert "Insufficient balance" in result["message"]


@pytest.mark.unit
def test_payment_without_finance_available_fails_cleanly(monkeypatch):
    monkeypatch.setattr(payments, "_finance", lambda: None)

    result = payments.take_payment(
        method=payments.CASH, amount=10.0, student_id="S12345",
        trip_id=1, trip_name="Museum Day",
    )

    assert result["success"] is False
    assert result["message"]


# ---------------------------------------------------------------------------
# Finance holds
# ---------------------------------------------------------------------------

class _Bus:
    def __init__(self, holds):
        self._holds = holds

    def list_active_holds(self, student_id):
        return self._holds


@pytest.mark.unit
def test_active_holds_are_reported(monkeypatch):
    monkeypatch.setattr(payments, "_finance_bus",
                        lambda: _Bus([{"reason": "Unpaid tuition", "amount": 250.0,
                                       "source": "Tuition"}]))

    holds = payments.active_holds("S12345")

    assert len(holds) == 1
    assert payments.describe_holds(holds) == ["  - Unpaid tuition (£250.00, from Tuition)"]


@pytest.mark.unit
def test_hold_check_fails_open_when_the_bus_is_unavailable(monkeypatch):
    # An unreachable finance bus must not lock everyone out of trips.
    monkeypatch.setattr(payments, "_finance_bus", lambda: None)
    assert payments.active_holds("S12345") == []


# ---------------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_student_account_refund_credits_the_balance_back(finance):
    stub = finance(balance=50.0)

    result = payments.refund_payment(
        method=payments.STUDENT_ACCOUNT, amount=50.0, student_id="S12345",
        trip_id=1, trip_name="Museum Day", payment_reference="Trips_TRIP-1",
    )

    assert result["success"] is True
    assert result["refund_id"] == 7
    assert result["reference"] == "TRIPS-TRIP-1"
    assert result["balance_after"] == 100.0
    assert [kind for kind, _ in stub.calls] == ["refund", "topup"]


@pytest.mark.unit
def test_till_refund_is_recorded_against_the_original_method(finance):
    stub = finance(balance=None)

    result = payments.refund_payment(
        method=payments.CARD, amount=80.0, student_id="S12345",
        trip_id=2, trip_name="Expensive Trip",
    )

    assert result["success"] is True
    # No balance to move — the finance office settles it.
    assert result["balance_after"] is None
    assert [kind for kind, _ in stub.calls] == ["refund"]
    _, kwargs = stub.calls[0]
    assert kwargs["refund_method"] == "Card"
    assert kwargs["transaction_source"] == payments.TRANSACTION_SOURCE


@pytest.mark.unit
def test_refund_recorded_but_not_credited_is_reported_as_a_failure(finance):
    finance(balance=50.0, topup_ok=False)

    result = payments.refund_payment(
        method=payments.STUDENT_ACCOUNT, amount=50.0, student_id="S12345",
        trip_id=1, trip_name="Museum Day",
    )

    assert result["success"] is False
    assert "account closed" in result["message"]
