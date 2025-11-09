"""
Finance Integration Utility Module

This module provides functions for integrating various university subsystems
with the central finance module. It ensures all financial transactions are
properly recorded in the main finance system for unified reporting and tracking.

Usage:
    from university_system.modules.shared.utils.finance_integration import record_payment_to_finance

    # Record a payment from any subsystem
    payment_id = record_payment_to_finance(
        student_id="S001",
        amount=250.00,
        payment_method="Credit Card",
        transaction_source="Library",
        transaction_ref="FINE-12345",
        notes="Late return fine for 3 books"
    )
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal

# Import database connection from finance module
try:
    from university_system.modules.domain.finance.finance_misc.finance_db_operations import get_finance_db_connection
except ImportError:
    # Fallback to standard database connection
    from university_system.infrastructure.database.db import get_connection as get_finance_db_connection

from university_system.modules.shared.constants import paths

logger = logging.getLogger(__name__)


def record_payment_to_finance(
    student_id: str,
    amount: float,
    payment_method: str,
    transaction_source: str,
    transaction_ref: str,
    currency: str = "GBP",
    status: str = "completed",
    notes: Optional[str] = None,
    created_by: Optional[str] = None,
    payment_date: Optional[str] = None
) -> Optional[int]:
    """
    Record a payment transaction to the central finance system.

    Args:
        student_id: Student ID making the payment
        amount: Payment amount
        payment_method: Method of payment (e.g., "Credit Card", "Cash", "Bank Transfer")
        transaction_source: Source system (e.g., "Library", "Housing", "Shop", "Restaurant")
        transaction_ref: Reference ID from source system (e.g., "FINE-12345", "RENT-2024-01")
        currency: Currency code (default: "GBP")
        status: Payment status (default: "completed")
        notes: Additional notes about the payment
        created_by: User ID who processed the payment
        payment_date: Date of payment (default: current timestamp)

    Returns:
        payment_id: ID of the recorded payment in finance system, or None if failed
    """
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Prepare payment date
        if payment_date is None:
            payment_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Construct comprehensive notes
        full_notes = f"[{transaction_source}] Ref: {transaction_ref}"
        if notes:
            full_notes += f" - {notes}"

        # Insert payment into finance system
        cursor.execute('''
        INSERT INTO payments (
            student_id, amount, currency, payment_method, transaction_id,
            payment_date, status, notes, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            student_id,
            round(float(amount), 2),
            currency,
            payment_method,
            f"{transaction_source}-{transaction_ref}",
            payment_date,
            status,
            full_notes,
            created_by or "System",
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        payment_id = cursor.lastrowid

        conn.commit()
        conn.close()

        logger.info(f"Recorded payment to finance: {transaction_source} - {transaction_ref} - £{amount} (Payment ID: {payment_id})")

        return payment_id

    except sqlite3.Error as e:
        logger.error(f"Error recording payment to finance: {e}")
        if 'conn' in locals():
            conn.close()
        return None
    except Exception as e:
        logger.error(f"Unexpected error in record_payment_to_finance: {e}")
        return None


def record_refund_to_finance(
    student_id: str,
    refund_amount: float,
    original_payment_id: Optional[int],
    refund_reason: str,
    refund_type: str,
    transaction_source: str,
    transaction_ref: str,
    refund_method: str = "original_payment_method",
    currency: str = "GBP",
    requested_by: Optional[str] = None,
    notes: Optional[str] = None
) -> Optional[int]:
    """
    Record a refund transaction to the central finance system.

    Args:
        student_id: Student ID receiving the refund
        refund_amount: Amount to refund
        original_payment_id: ID of original payment in finance system (if known)
        refund_reason: Reason for refund
        refund_type: Type of refund ('full', 'partial', 'withdrawal')
        transaction_source: Source system
        transaction_ref: Reference ID from source system
        refund_method: Method of refund
        currency: Currency code
        requested_by: User ID who requested refund
        notes: Additional notes

    Returns:
        refund_id: ID of the recorded refund, or None if failed
    """
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Construct comprehensive notes
        full_notes = f"[{transaction_source}] Ref: {transaction_ref}"
        if notes:
            full_notes += f" - {notes}"

        # Insert refund into finance system
        cursor.execute('''
        INSERT INTO refunds (
            student_id, original_payment_id, refund_amount, currency, refund_reason,
            refund_type, refund_method, status, requested_by, request_date,
            approved_by, approval_date, processed_by, processed_date,
            notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            student_id,
            original_payment_id,
            round(float(refund_amount), 2),
            currency,
            refund_reason,
            refund_type,
            refund_method,
            "processed",  # Auto-approved since coming from subsystems
            requested_by or "System",
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "System",  # Auto-approved
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "System",  # Auto-processed
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            full_notes,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        refund_id = cursor.lastrowid

        conn.commit()
        conn.close()

        logger.info(f"Recorded refund to finance: {transaction_source} - {transaction_ref} - £{refund_amount} (Refund ID: {refund_id})")

        return refund_id

    except sqlite3.Error as e:
        logger.error(f"Error recording refund to finance: {e}")
        if 'conn' in locals():
            conn.close()
        return None
    except Exception as e:
        logger.error(f"Unexpected error in record_refund_to_finance: {e}")
        return None


def record_revenue_to_finance(
    student_id: str,
    amount: float,
    revenue_category: str,
    transaction_source: str,
    transaction_ref: str,
    payment_method: str = "Cash",
    currency: str = "GBP",
    notes: Optional[str] = None
) -> Optional[int]:
    """
    Record a revenue transaction (donation, sale, etc.) to the central finance system.

    Args:
        student_id: Student ID or "EXTERNAL" for non-student transactions
        amount: Revenue amount
        revenue_category: Category of revenue (e.g., "Donation", "Sale", "Service")
        transaction_source: Source system
        transaction_ref: Reference ID from source system
        payment_method: Method of payment
        currency: Currency code
        notes: Additional notes

    Returns:
        payment_id: ID of the recorded payment, or None if failed
    """
    full_notes = f"Revenue - {revenue_category}"
    if notes:
        full_notes += f" - {notes}"

    return record_payment_to_finance(
        student_id=student_id,
        amount=amount,
        payment_method=payment_method,
        transaction_source=transaction_source,
        transaction_ref=transaction_ref,
        currency=currency,
        status="completed",
        notes=full_notes
    )


def get_student_financial_summary(student_id: str) -> Dict[str, Any]:
    """
    Get a summary of all financial transactions for a student across all systems.

    Args:
        student_id: Student ID

    Returns:
        Dictionary with financial summary
    """
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Get total payments
        cursor.execute('''
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM payments
        WHERE student_id = ? AND status = 'completed'
        ''', (student_id,))
        payment_count, total_paid = cursor.fetchone()

        # Get total refunds
        cursor.execute('''
        SELECT COUNT(*), COALESCE(SUM(refund_amount), 0)
        FROM refunds
        WHERE student_id = ? AND status = 'processed'
        ''', (student_id,))
        refund_count, total_refunded = cursor.fetchone()

        # Get payments by source
        cursor.execute('''
        SELECT
            CASE
                WHEN notes LIKE '[Library]%' THEN 'Library'
                WHEN notes LIKE '[Housing]%' THEN 'Housing'
                WHEN notes LIKE '[Shop]%' THEN 'Shop'
                WHEN notes LIKE '[Restaurant]%' THEN 'Restaurant'
                WHEN notes LIKE '[Student Union]%' THEN 'Student Union'
                WHEN notes LIKE '[Alumni]%' THEN 'Alumni'
                ELSE 'Other'
            END as source,
            COUNT(*),
            COALESCE(SUM(amount), 0)
        FROM payments
        WHERE student_id = ? AND status = 'completed'
        GROUP BY source
        ''', (student_id,))
        payments_by_source = cursor.fetchall()

        conn.close()

        return {
            'student_id': student_id,
            'total_payments': payment_count or 0,
            'total_paid': round(float(total_paid or 0), 2),
            'total_refunds': refund_count or 0,
            'total_refunded': round(float(total_refunded or 0), 2),
            'net_paid': round(float((total_paid or 0) - (total_refunded or 0)), 2),
            'payments_by_source': {
                source: {'count': count, 'amount': round(float(amount), 2)}
                for source, count, amount in payments_by_source
            }
        }

    except sqlite3.Error as e:
        logger.error(f"Error getting financial summary: {e}")
        return {}


def get_finance_report_by_source(
    transaction_source: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get financial report for a specific transaction source.

    Args:
        transaction_source: Source system (e.g., "Library", "Housing")
        start_date: Start date filter (YYYY-MM-DD)
        end_date: End date filter (YYYY-MM-DD)

    Returns:
        Dictionary with financial report
    """
    try:
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Build query with date filters
        query = '''
        SELECT
            COUNT(*),
            COALESCE(SUM(amount), 0),
            AVG(amount),
            MIN(amount),
            MAX(amount)
        FROM payments
        WHERE notes LIKE ? AND status = 'completed'
        '''
        params = [f'[{transaction_source}]%']

        if start_date:
            query += ' AND payment_date >= ?'
            params.append(start_date)

        if end_date:
            query += ' AND payment_date <= ?'
            params.append(end_date)

        cursor.execute(query, params)
        count, total, avg, min_amt, max_amt = cursor.fetchone()

        conn.close()

        return {
            'source': transaction_source,
            'transaction_count': count or 0,
            'total_revenue': round(float(total or 0), 2),
            'average_transaction': round(float(avg or 0), 2),
            'min_transaction': round(float(min_amt or 0), 2),
            'max_transaction': round(float(max_amt or 0), 2),
            'start_date': start_date,
            'end_date': end_date
        }

    except sqlite3.Error as e:
        logger.error(f"Error generating finance report: {e}")
        return {}
