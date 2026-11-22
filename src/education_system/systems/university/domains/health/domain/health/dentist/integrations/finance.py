"""Dentist -> Finance bridge.

The dental clinic's only outward dependency on Finance lives here, so the
service layer (``services/dentist_core.py``) can post to the general ledger
without importing Finance itself. Both hooks are fire-and-forget: a posting
failure is logged by ``notify_ledger`` and never raises.
"""


def notify_payment(payment_row_id, processed_by):
    """Post a ``payments`` row written by the clinic to the GL."""
    from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
    return notify_ledger("payment", payment_row_id, posted_by=processed_by or "dentist")


def notify_refund(transaction_id, processed_by):
    from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
    return notify_ledger("refund", transaction_id, posted_by=processed_by)
