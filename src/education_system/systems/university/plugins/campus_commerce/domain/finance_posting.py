"""Finance posting shared by the campus-commerce domain services.

Plugins may only reach Finance through the public functions in
``finance.infrastructure.finance_integration`` (plus ``notify_ledger``,
which those functions fire themselves). Each shop's *domain service* calls
these helpers exactly once per money action, so the GUI and CLI twins
share one posting and nothing posts twice. Interfaces never post.

A posting failure never rolls back the local sale: it is logged and
reported in the returned dict. The one exception is a student-account
payment, where the debit *is* the payment - if it fails no money moved, so
``success`` is False and the caller should not record the sale.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_STUDENT_ACCOUNT_METHODS = frozenset({
    'student_account', 'student_finance_account', 'finance_account',
    'student_finance', 'studentaccount',
})


def is_student_account(payment_method: Optional[str]) -> bool:
    """True when ``payment_method`` names the student finance account."""
    if not payment_method:
        return False
    return payment_method.strip().lower().replace(' ', '_').replace('-', '_') in _STUDENT_ACCOUNT_METHODS


def post_sale(
    *,
    student_id: str,
    amount: float,
    payment_method: str,
    transaction_source: str,
    transaction_ref: str,
    description: str,
    processed_by: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Post a completed sale to Finance.

    Student-account methods debit the account via
    ``process_student_finance_account_payment`` (which records the finance
    payment itself); anything else goes through ``record_payment_to_finance``.

    Returns ``{'success', 'payment_id', 'message', 'student_account', 'new_balance'}``.
    """
    result: Dict[str, Any] = {
        'success': True, 'payment_id': None, 'message': '',
        'student_account': is_student_account(payment_method), 'new_balance': None,
    }
    try:
        from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
            process_student_finance_account_payment,
            record_payment_to_finance,
        )
    except ImportError as exc:  # finance domain not installed
        logger.warning("%s: finance integration unavailable, sale %s not posted: %s",
                       transaction_source, transaction_ref, exc)
        result['message'] = 'Finance integration unavailable'
        return result

    if result['student_account']:
        try:
            outcome = process_student_finance_account_payment(
                student_id=str(student_id),
                amount=float(amount),
                description=description,
                transaction_source=transaction_source,
                transaction_ref=transaction_ref,
                processed_by=processed_by or 'System',
            )
        except Exception as exc:
            logger.warning("%s: student-account payment %s failed: %s",
                           transaction_source, transaction_ref, exc)
            result.update(success=False, message=str(exc))
            return result
        result['success'] = bool(outcome.get('success'))
        result['message'] = outcome.get('message', '')
        result['payment_id'] = outcome.get('transaction_id')
        result['new_balance'] = outcome.get('new_balance')
        if not result['success']:
            logger.warning("%s: student-account payment %s declined: %s",
                           transaction_source, transaction_ref, result['message'])
        return result

    try:
        payment_id = record_payment_to_finance(
            student_id=str(student_id),
            amount=float(amount),
            payment_method=_display_method(payment_method),
            transaction_source=transaction_source,
            transaction_ref=transaction_ref,
            notes=_join_notes(description, notes),
            created_by=processed_by,
        )
    except Exception as exc:
        logger.warning("%s: finance posting for %s failed: %s",
                       transaction_source, transaction_ref, exc)
        result['message'] = str(exc)
        return result
    if payment_id is None:
        logger.warning("%s: finance posting for %s returned no payment id",
                       transaction_source, transaction_ref)
        result['message'] = 'Finance posting failed'
    result['payment_id'] = payment_id
    return result


def post_refund(
    *,
    student_id: Optional[str],
    amount: float,
    transaction_source: str,
    transaction_ref: str,
    refund_method: str,
    reason: str,
    refund_type: str = 'full',
    processed_by: Optional[str] = None,
    notes: Optional[str] = None,
    original_payment_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Post a refund to Finance via ``record_refund_to_finance``.

    When ``refund_method`` is the student account the amount is also
    credited back with ``top_up_student_finance_account``.

    Returns ``{'refund_id', 'credited', 'new_balance', 'message'}``.
    """
    result: Dict[str, Any] = {
        'refund_id': None, 'credited': False, 'new_balance': None, 'message': '',
        'account_created': False,
    }
    try:
        from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
            record_refund_to_finance,
            top_up_student_finance_account,
        )
    except ImportError as exc:
        logger.warning("%s: finance integration unavailable, refund %s not posted: %s",
                       transaction_source, transaction_ref, exc)
        result['message'] = 'Finance integration unavailable'
        return result

    try:
        result['refund_id'] = record_refund_to_finance(
            student_id=str(student_id) if student_id else 'EXTERNAL',
            refund_amount=float(amount),
            original_payment_id=original_payment_id,
            refund_reason=reason,
            refund_type=refund_type,
            transaction_source=transaction_source,
            transaction_ref=transaction_ref,
            refund_method=refund_method,
            requested_by=processed_by,
            notes=notes,
        )
    except Exception as exc:
        logger.warning("%s: finance refund posting for %s failed: %s",
                       transaction_source, transaction_ref, exc)
        result['message'] = str(exc)

    if student_id and is_student_account(refund_method):
        try:
            outcome = top_up_student_finance_account(
                create_if_missing=True,
                student_id=str(student_id),
                amount=float(amount),
                payment_method='refund',
                processed_by=processed_by or 'System',
                description=f"{transaction_source} refund {transaction_ref}",
            )
            result['credited'] = bool(outcome.get('success'))
            result['account_created'] = bool(outcome.get('account_created'))
            result['new_balance'] = outcome.get('new_balance')
            if not result['credited']:
                result['message'] = outcome.get('message', '')
                logger.warning("%s: student-account credit for refund %s failed: %s",
                               transaction_source, transaction_ref, result['message'])
        except Exception as exc:
            logger.warning("%s: student-account credit for refund %s failed: %s",
                           transaction_source, transaction_ref, exc)
            result['message'] = str(exc)
    return result


def _display_method(payment_method: Optional[str]) -> str:
    method = (payment_method or 'Cash').strip()
    return method.replace('_', ' ').title() if method.islower() else method


def _join_notes(description: Optional[str], notes: Optional[str]) -> Optional[str]:
    parts = [p for p in (description, notes) if p]
    return ' - '.join(parts) if parts else None
