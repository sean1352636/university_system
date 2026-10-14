"""Regression tests ensuring finance compatibility operations do real work."""

from unittest.mock import MagicMock, patch

import pytest

from education_system.systems.university.domains.finance.interfaces.gui.finance import common_imports


def _transaction_context(connection):
    context = MagicMock()
    context.__enter__.return_value = connection
    context.__exit__.return_value = False
    return context


def test_stripe_adapter_returns_real_transaction_identifier():
    with patch.object(
        common_imports,
        "_process_stripe_payment",
        return_value={"success": True, "transaction_id": "pi_123"},
    ):
        result = common_imports.process_stripe_payment("S1", 12.50, "pm_123")

    assert result["id"] == "pi_123"


def test_stripe_adapter_raises_instead_of_reporting_false_success():
    with patch.object(
        common_imports,
        "_process_stripe_payment",
        return_value={"success": False, "error": "declined"},
    ):
        with pytest.raises(RuntimeError, match="declined"):
            common_imports.process_stripe_payment("S1", 12.50, "pm_bad")


def test_loan_payment_updates_payment_and_balance_in_one_transaction():
    connection = MagicMock()
    loan_result = MagicMock()
    loan_result.fetchone.return_value = ("S1", 1000, 250)
    connection.execute.side_effect = [loan_result, MagicMock(), MagicMock()]

    with patch.object(
        common_imports, "transaction", return_value=_transaction_context(connection)
    ):
        assert common_imports.process_loan_payment(7, 100, "bank_transfer") is True

    assert connection.execute.call_count == 3
    update_params = connection.execute.call_args_list[2].args[1]
    assert update_params[0] == 100.0
    assert update_params[2] == 7


def test_loan_payment_rejects_overpayment_before_any_write():
    connection = MagicMock()
    loan_result = MagicMock()
    loan_result.fetchone.return_value = ("S1", 500, 450)
    connection.execute.return_value = loan_result

    with patch.object(
        common_imports, "transaction", return_value=_transaction_context(connection)
    ):
        with pytest.raises(ValueError, match="exceeds"):
            common_imports.process_loan_payment(7, 100, "bank_transfer")

    assert connection.execute.call_count == 1


def test_duplicate_email_and_sms_configuration_is_not_exported():
    removed = {
        "setup_email_config",
        "setup_sms_config",
        "test_email_service",
        "test_sms_service",
    }
    assert removed.isdisjoint(common_imports.__all__)
