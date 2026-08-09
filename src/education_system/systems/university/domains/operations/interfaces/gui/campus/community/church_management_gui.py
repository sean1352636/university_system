"""Backward-compatible entry point for church management."""

from .church_management.app import ChurchManagementSystem, main
from .church_management.persistence.schema import (
    CHURCH_MANAGEMENT_SCHEMA,
    init_church_database,
)
from .church_management.services.payments import (
    get_student_account_balance,
    process_student_payment,
    record_revenue,
)
from .church_management.services.receipts import send_receipt_email
from .church_management.services.user_context import get_current_user
from .church_management.ui.dialogs.payment_dialog import PaymentDialog

__all__ = [
    "ChurchManagementSystem",
    "PaymentDialog",
    "CHURCH_MANAGEMENT_SCHEMA",
    "init_church_database",
    "get_current_user",
    "get_student_account_balance",
    "process_student_payment",
    "record_revenue",
    "send_receipt_email",
    "main",
]


if __name__ == "__main__":
    main()
