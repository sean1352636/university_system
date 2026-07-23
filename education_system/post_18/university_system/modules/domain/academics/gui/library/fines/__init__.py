"""Library fines management subpackage — canonical aggregator.

Re-exports the public surface of the sibling modules (display, refunds,
payments, finance_integration, admin) so callers can use
``from ...library.fines import show_fine_management, refund_fine_dialog, …``
as a single import. This is the public API for the subpackage, not a
deprecated shim.
"""

from education_system.post_18.university_system.modules.domain.academics.gui.library.fines.display import show_fine_management, load_user_fines
from education_system.post_18.university_system.modules.domain.academics.gui.library.fines.refunds import (
    refund_fine_dialog,
    _show_user_refund_details,
    _process_library_fine_refund,
    _send_refund_receipt_email,
)
from education_system.post_18.university_system.modules.domain.academics.gui.library.fines.payments import (
    process_fine_payment,
    pay_fine_from_finance_account,
    process_fine_payment_gui,
)
from education_system.post_18.university_system.modules.domain.academics.gui.library.fines.finance_integration import (
    _show_topup_dialog,
    pay_fine_via_finance,
    _process_library_fine_payment,
    open_finance_payment_for_user,
)
from education_system.post_18.university_system.modules.domain.academics.gui.library.fines.admin import waive_all_fines, view_fine_history, adjust_fine_amount
from education_system.post_18.university_system.modules.domain.academics.gui.library.fines.reports import generate_fine_statistics_report, export_fines_to_csv, _save_text_report
from education_system.post_18.university_system.modules.domain.academics.gui.library.fines.recording import _record_fine_payment, _record_library_payment_in_finance
from education_system.post_18.university_system.modules.domain.academics.gui.library.fines.receipts import generate_fine_receipt_gui

__all__ = [
    # display
    'show_fine_management',
    'load_user_fines',
    # refunds
    'refund_fine_dialog',
    '_show_user_refund_details',
    '_process_library_fine_refund',
    '_send_refund_receipt_email',
    # payments
    'process_fine_payment',
    'pay_fine_from_finance_account',
    'process_fine_payment_gui',
    # finance integration
    '_show_topup_dialog',
    'pay_fine_via_finance',
    '_process_library_fine_payment',
    'open_finance_payment_for_user',
    # admin
    'waive_all_fines',
    'view_fine_history',
    'adjust_fine_amount',
    # reports
    'generate_fine_statistics_report',
    'export_fines_to_csv',
    '_save_text_report',
    # recording
    '_record_fine_payment',
    '_record_library_payment_in_finance',
    # receipts
    'generate_fine_receipt_gui',
]
