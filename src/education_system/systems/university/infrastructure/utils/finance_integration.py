"""
Finance Integration Utility Module

This module provides functions for integrating various university subsystems
with the central finance module. It ensures all financial transactions are
properly recorded in the main finance system for unified reporting and tracking.

Usage:
    from education_system.systems.university.infrastructure.utils.finance_integration import record_payment_to_finance

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

from education_system.systems.university.infrastructure.database.db import sqlite3
import html
import logging
import math
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
from decimal import Decimal

# Import database connection from finance module
try:
    from education_system.systems.university.domain.finance.core.finance_db_operations import get_finance_db_connection
except ImportError:
    # Fallback to standard database connection
    from education_system.systems.university.infrastructure.database.db import get_connection as get_finance_db_connection

# Import transaction context manager for write operations
from education_system.systems.university.infrastructure.database.db import transaction

from education_system import paths

logger = logging.getLogger(__name__)

def _ensure_finance_tables_exist():
    """
    Ensure the student finance account tables exist in the database.
    Creates them if they don't exist.
    """
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            # Student finance accounts table - for student prepaid balance
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_finance_accounts (
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE NOT NULL,
                balance DECIMAL(10,2) DEFAULT 0.00,
                currency TEXT DEFAULT 'GBP',
                account_status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Note: student_finance_transactions now uses the unified 'transactions' table
            # with source_type = 'student_finance'. No separate table creation needed.

            # Main payments table for finance GUI
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                currency TEXT DEFAULT 'GBP',
                payment_method TEXT,
                gateway_transaction_id TEXT,
                gateway_name TEXT,
                transaction_id TEXT,
                payment_date TEXT,
                status TEXT DEFAULT 'completed',
                notes TEXT,
                created_by TEXT,
                created_at TEXT,
                fraud_score DECIMAL(3,2),
                is_suspicious BOOLEAN DEFAULT 0
            )
            ''')

            # Unified refunds table - replaces both finance_refunds and refunds tables
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_refunds (
                refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                refund_reference TEXT,
                source_type TEXT NOT NULL DEFAULT 'general',
                department TEXT,
                reference_id TEXT,
                reference_type TEXT,
                amount DECIMAL(10,2) NOT NULL,
                refund_type TEXT,
                refund_method TEXT,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                refund_date TEXT,
                request_date TEXT,
                approval_date TEXT,
                requested_by TEXT,
                approved_by TEXT,
                processed_by TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

        return True

    except sqlite3.Error as e:
        logger.error(f"Error creating finance tables: {e}")
        return False

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
        # Prepare payment date
        if payment_date is None:
            payment_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Construct comprehensive notes
        full_notes = f"[{transaction_source}] Ref: {transaction_ref}"
        if notes:
            full_notes += f" - {notes}"

        with transaction() as conn:
            cursor = conn.cursor()

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

        logger.info(f"Recorded payment to finance: {transaction_source} - {transaction_ref} - \u00a3{amount} (Payment ID: {payment_id})")

        # Auto-post to GL (no-op if ledger not initialised; never raises)
        if status == 'completed':
            try:
                from education_system.systems.university.domain.finance.ledger import notify_ledger
                notify_ledger('payment', payment_id, posted_by=created_by or 'auto')
            except Exception:
                logger.exception("ledger hook failed for payment %s", payment_id)

        return payment_id

    except sqlite3.Error as e:
        logger.error(f"Error recording payment to finance: {e}")
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
        # Construct comprehensive notes
        full_notes = f"{refund_reason}"
        if notes:
            full_notes += f" - {notes}"

        # Generate refund reference
        refund_reference = f"{transaction_source.upper()}-{transaction_ref}"

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with transaction() as conn:
            cursor = conn.cursor()

            # Insert refund into unified_refunds table
            cursor.execute('''
            INSERT INTO unified_refunds (
                student_id, refund_reference, source_type, department,
                reference_id, reference_type, amount, refund_type,
                refund_method, reason, status, refund_date,
                request_date, processed_by, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id,
                refund_reference,
                transaction_source.lower().replace(' ', '_'),
                transaction_source,
                str(original_payment_id) if original_payment_id else None,
                'payment' if original_payment_id else None,
                round(float(refund_amount), 2),
                refund_type,
                refund_method.lower().replace(' ', '_'),
                refund_reason,
                'processed',
                now,
                now,
                requested_by or "System",
                full_notes,
                now
            ))

            refund_id = cursor.lastrowid

        logger.info(f"Recorded refund to unified_refunds: {transaction_source} - {transaction_ref} - \u00a3{refund_amount} (Refund ID: {refund_id})")

        # Auto-post to GL \u2014 this helper inserts with status='processed', so cash has moved.
        try:
            from education_system.systems.university.domain.finance.ledger import notify_ledger
            notify_ledger('refund', refund_id, posted_by=requested_by or 'auto')
        except Exception:
            logger.exception("ledger hook failed for refund %s", refund_id)

        return refund_id

    except sqlite3.Error as e:
        logger.error(f"Error recording refund to finance: {e}")
        import traceback
        traceback.print_exc()
        return None
    except Exception as e:
        logger.error(f"Unexpected error in record_refund_to_finance: {e}")
        import traceback
        traceback.print_exc()
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
        with get_finance_db_connection() as conn:
            cursor = conn.cursor()

            # Get total payments
            cursor.execute('''
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM payments
            WHERE student_id = ? AND status = 'completed'
            ''', (student_id,))
            payment_count, total_paid = cursor.fetchone()

            # Get total refunds from unified_refunds
            cursor.execute('''
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM unified_refunds
            WHERE student_id = ? AND status IN ('processed', 'approved', 'completed')
            ''', (student_id,))
            refund_count, total_refunded = cursor.fetchone()

            # Get payments by source
            cursor.execute('''
            SELECT
                CASE
                    WHEN notes LIKE '[Library]%' THEN 'Library'
                    WHEN notes LIKE '[Housing]%' THEN 'Housing'
                    WHEN notes LIKE '[Shop]%' AND notes NOT LIKE '[Charity Shop]%'
                         AND notes NOT LIKE '[MusicShop]%' AND notes NOT LIKE '[PhoneShop]%' THEN 'Shop'
                    WHEN notes LIKE '[Restaurant]%' THEN 'Restaurant'
                    WHEN notes LIKE '[Student Union]%' THEN 'Student Union'
                    WHEN notes LIKE '[Alumni]%' THEN 'Alumni'
                    WHEN notes LIKE '[Trip Management]%' THEN 'Trip Management'
                    WHEN notes LIKE '[Cafe]%' THEN 'Cafe'
                    WHEN notes LIKE '[Grocery]%' THEN 'Grocery'
                    WHEN notes LIKE '[Takeaway]%' THEN 'Takeaway'
                    WHEN notes LIKE '[MusicShop]%' THEN 'MusicShop'
                    WHEN notes LIKE '[PhoneShop]%' THEN 'PhoneShop'
                    WHEN notes LIKE '[EquipmentRental]%' THEN 'EquipmentRental'
                    WHEN notes LIKE '[CarRental]%' THEN 'CarRental'
                    WHEN notes LIKE '[Charity Shop]%' THEN 'Charity Shop'
                    WHEN notes LIKE 'Dental:%' OR notes LIKE '[Dentist]%' THEN 'Dentist'
                    WHEN notes LIKE 'Gym:%' OR notes LIKE '[Gym]%' THEN 'Gym'
                    WHEN notes LIKE '[Bar]%' THEN 'Bar'
                    WHEN notes LIKE '[Parking]%' THEN 'Parking'
                    WHEN notes LIKE '[Betting]%' THEN 'Betting'
                    WHEN notes LIKE '[Butcher]%' OR notes LIKE 'Butcher%' THEN 'Butcher'
                    WHEN notes LIKE '[Barber]%' OR notes LIKE 'Barber%' THEN 'Barber'
                    WHEN notes LIKE '[NailBar]%' OR notes LIKE 'NailBar%' OR notes LIKE 'Nail Bar%' THEN 'NailBar'
                    ELSE 'Other'
                END as source,
                COUNT(*),
                COALESCE(SUM(amount), 0)
            FROM payments
            WHERE student_id = ? AND status = 'completed'
            GROUP BY source
            ''', (student_id,))
            payments_by_source = cursor.fetchall()

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
        with get_finance_db_connection() as conn:
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

# Low Balance Threshold (in GBP)
LOW_BALANCE_THRESHOLD = 20.00

def get_student_email(student_id: str) -> Optional[str]:
    """
    Get student's email address from the database.
    Checks both students table and users table.

    Args:
        student_id: Student ID or username

    Returns:
        Email address or None if not found
    """
    try:
        with get_finance_db_connection() as conn:
            cursor = conn.cursor()

            # First try the students table
            cursor.execute("PRAGMA table_info(students)")
            columns = [col[1] for col in cursor.fetchall()]

            # Try column names in order of likelihood (email_address is most common)
            for email_col in ['email_address', 'email', 'student_email']:
                if email_col in columns:
                    safe_col = validate_identifier(email_col, "column")
                    cursor.execute('SELECT ' + safe_col + ' FROM students WHERE student_id = ?', (student_id,))
                    result = cursor.fetchone()
                    if result and result[0]:
                        return result[0]
                    break  # Column exists but no value

            # Fallback: check users table by student_id or username
            cursor.execute('SELECT email FROM users WHERE student_id = ? OR username = ?', (student_id, student_id))
            result = cursor.fetchone()
            if result and result[0]:
                return result[0]

        return None

    except sqlite3.Error as e:
        logger.error(f"Error getting student email: {e}")
        return None

def get_student_info(student_id: str) -> Optional[Dict[str, Any]]:
    """
    Get student's basic information from the database.
    Checks both students table and users table.

    Args:
        student_id: Student ID or username

    Returns:
        Dictionary with student info or None if not found
    """
    try:
        with get_finance_db_connection() as conn:
            cursor = conn.cursor()

            # First try the students table
            cursor.execute("PRAGMA table_info(students)")
            columns = [col[1] for col in cursor.fetchall()]

            # Determine email column name
            email_col = 'email_address' if 'email_address' in columns else 'email' if 'email' in columns else None

            if email_col:
                validate_identifier(email_col, "column")
                cursor.execute(f'''
                    SELECT student_id, first_name, last_name, {email_col}
                    FROM students WHERE student_id = ?
                ''', (student_id,))
            else:
                cursor.execute('''
                    SELECT student_id, first_name, last_name
                    FROM students WHERE student_id = ?
                ''', (student_id,))

            result = cursor.fetchone()

            if result:
                return {
                    'student_id': result[0],
                    'first_name': result[1],
                    'last_name': result[2],
                    'email': result[3] if len(result) > 3 else None,
                    'full_name': f"{result[1]} {result[2]}"
                }

            # Fallback: check users table by student_id or username
            cursor.execute('''
                SELECT username, first_name, last_name, email, student_id
                FROM users WHERE student_id = ? OR username = ?
            ''', (student_id, student_id))
            result = cursor.fetchone()

            if result:
                return {
                    'student_id': result[4] or result[0],  # Use student_id if available, else username
                    'first_name': result[1],
                    'last_name': result[2],
                    'email': result[3],
                    'full_name': f"{result[1]} {result[2]}"
                }

        return None

    except sqlite3.Error as e:
        logger.error(f"Error getting student info: {e}")
        return None

def get_student_finance_account_balance(student_id: str) -> Optional[float]:
    """
    Get student's finance account balance.

    Args:
        student_id: Student ID

    Returns:
        Account balance or None if account doesn't exist
    """
    try:
        # Ensure tables exist first
        _ensure_finance_tables_exist()

        with get_finance_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT balance FROM student_finance_accounts WHERE student_id = ?
            ''', (student_id,))
            result = cursor.fetchone()

            if result:
                return float(result[0])
        return None

    except sqlite3.Error as e:
        logger.error(f"Error getting student finance account balance: {e}")
        return None

def ensure_student_finance_account_exists(student_id: str) -> bool:
    """
    Ensure a finance account exists for the student, creating one if needed.
    Also ensures the required tables exist.

    Args:
        student_id: Student ID

    Returns:
        True if account exists or was created, False on error
    """
    try:
        # Ensure tables exist first
        _ensure_finance_tables_exist()

        with transaction() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR IGNORE INTO student_finance_accounts (student_id, balance)
                VALUES (?, 0.00)
            ''', (student_id,))

        return True

    except sqlite3.Error as e:
        logger.error(f"Error ensuring student account exists: {e}")
        return False

def send_payment_receipt_email(
    student_id: str,
    amount: float,
    description: str,
    transaction_source: str,
    transaction_id: str,
    balance_before: float,
    balance_after: float
) -> bool:
    """
    Send a payment receipt email to the student.

    Args:
        student_id: Student ID
        amount: Payment amount
        description: Payment description
        transaction_source: Source system (e.g., "Shop", "Restaurant", "Library")
        transaction_id: Transaction ID/reference
        balance_before: Balance before payment
        balance_after: Balance after payment

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get student info
        student_info = get_student_info(student_id)
        if not student_info or not student_info.get('email'):
            logger.warning(f"Cannot send payment receipt: No email found for student {student_id}")
            return False

        student_email = student_info['email']
        student_name = student_info.get('full_name', 'Student')

        # Try to use email service
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            subject = f"Payment Receipt - {transaction_source}"
            body = f"""Dear {student_name},

This is a confirmation of your recent payment from your Student Finance Account.

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
                    PAYMENT RECEIPT
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

Transaction Details:
--------------------
Transaction ID:     {transaction_id}
Date & Time:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source:             {transaction_source}
Description:        {description}

Payment Amount:     \u00a3{amount:.2f}

Account Summary:
----------------
Previous Balance:   \u00a3{balance_before:.2f}
Payment Amount:     -\u00a3{amount:.2f}
Current Balance:    \u00a3{balance_after:.2f}

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

If you did not make this payment or have any questions, please contact the Finance Office immediately.

To top up your account, please visit the Finance Office or use the online portal.

Best regards,
University Finance Department

---
This is an automated receipt. Please do not reply to this email.
"""

            result = send_email(student_email, subject, body)
            if result:
                logger.info(f"Payment receipt email sent to {student_email} for transaction {transaction_id}")
                return True
            else:
                logger.warning(f"Failed to send payment receipt email to {student_email}")
                return False

        except ImportError:
            logger.warning("Email service not available for payment receipt")
            return False

    except Exception as e:
        logger.error(f"Error sending payment receipt email: {e}")
        return False

def send_topup_confirmation_email(
    student_id: str,
    amount: float,
    payment_method: str,
    balance_before: float,
    balance_after: float
) -> bool:
    """
    Send a top-up confirmation email to the student.

    Args:
        student_id: Student ID
        amount: Top-up amount
        payment_method: Method of top-up (e.g., "card", "cash", "bank_transfer")
        balance_before: Balance before top-up
        balance_after: Balance after top-up

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get student info
        student_info = get_student_info(student_id)
        if not student_info or not student_info.get('email'):
            logger.warning(f"Cannot send top-up confirmation: No email found for student {student_id}")
            return False

        student_email = student_info['email']
        student_name = student_info.get('full_name', 'Student')

        # Try to use email service
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            subject = "Account Top-Up Confirmation - Student Finance Account"
            body = f"""Dear {student_name},

Your Student Finance Account has been successfully topped up.

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
              ACCOUNT TOP-UP CONFIRMATION
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

Top-Up Details:
---------------
Date & Time:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Payment Method:     {payment_method.replace('_', ' ').title()}
Amount Added:       \u00a3{amount:.2f}

Account Summary:
----------------
Previous Balance:   \u00a3{balance_before:.2f}
Amount Added:       +\u00a3{amount:.2f}
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
NEW BALANCE:        \u00a3{balance_after:.2f}
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

Your funds are now available for use at:
\u2022 Campus Shop
\u2022 University Restaurant & Dining
\u2022 Library (fines & printing)
\u2022 Student Union activities
\u2022 Housing payments

If you did not authorize this top-up, please contact the Finance Office immediately.

Best regards,
University Finance Department

---
This is an automated confirmation. Please do not reply to this email.
"""

            result = send_email(student_email, subject, body)
            if result:
                logger.info(f"Top-up confirmation email sent to {student_email} for \u00a3{amount:.2f}")
                return True
            else:
                logger.warning(f"Failed to send top-up confirmation email to {student_email}")
                return False

        except ImportError:
            logger.warning("Email service not available for top-up confirmation")
            return False

    except Exception as e:
        logger.error(f"Error sending top-up confirmation email: {e}")
        return False

def send_low_balance_email(student_id: str, current_balance: float, threshold: float = LOW_BALANCE_THRESHOLD) -> bool:
    """
    Send a low balance notification email to the student.

    Args:
        student_id: Student ID
        current_balance: Current account balance
        threshold: Low balance threshold (default: LOW_BALANCE_THRESHOLD)

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get student info
        student_info = get_student_info(student_id)
        if not student_info or not student_info.get('email'):
            logger.warning(f"Cannot send low balance email: No email found for student {student_id}")
            return False

        student_email = student_info['email']
        student_name = student_info.get('full_name', 'Student')

        # Try to use email service
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            subject = "Low Balance Alert - Student Finance Account"
            body = f"""Dear {student_name},

This is an automated notification to inform you that your Student Finance Account balance is running low.

Current Balance: \u00a3{current_balance:.2f}
Low Balance Threshold: \u00a3{threshold:.2f}

We recommend topping up your account to ensure uninterrupted access to university services including:
- Campus shop purchases
- Restaurant and dining services
- Library fines
- Housing payments
- Student Union activities

To add funds to your account, please visit the Finance Office or use the online top-up facility through the Student Portal.

If you have any questions, please contact the Finance Office.

Best regards,
University Finance Department

---
This is an automated message. Please do not reply to this email.
"""

            result = send_email(student_email, subject, body)
            if result:
                logger.info(f"Low balance email sent to {student_email} for student {student_id}")
                return True
            else:
                logger.warning(f"Failed to send low balance email to {student_email}")
                return False

        except ImportError:
            logger.warning("Email service not available for low balance notification")
            return False

    except Exception as e:
        logger.error(f"Error sending low balance email: {e}")
        return False

def process_student_finance_account_payment(
    student_id: str,
    amount: float,
    description: str,
    transaction_source: str,
    transaction_ref: str,
    processed_by: str = "System",
    check_balance: bool = True,
    send_low_balance_alert: bool = True
) -> Dict[str, Any]:
    """
    Process a payment from student's finance account balance.

    This function deducts the specified amount from the student's finance account,
    records the transaction, and sends a low balance email if the balance falls
    below the threshold.

    Args:
        student_id: Student ID
        amount: Amount to deduct
        description: Description of the payment
        transaction_source: Source system (e.g., "Shop", "Restaurant", "Library")
        transaction_ref: Reference ID from source system
        processed_by: Username of person processing the payment
        check_balance: If True, verify sufficient balance before payment
        send_low_balance_alert: If True, send email when balance falls below threshold

    Returns:
        Dictionary with:
            - success: bool - Whether the payment was successful
            - message: str - Status message
            - new_balance: float - Balance after transaction (if successful)
            - transaction_id: str - Transaction ID (if successful)
            - email_sent: bool - Whether low balance email was sent
    """
    result = {
        'success': False,
        'message': '',
        'new_balance': None,
        'transaction_id': None,
        'email_sent': False
    }

    try:
        # Validate amount
        if amount <= 0:
            result['message'] = "Payment amount must be positive"
            return result

        # Ensure account exists
        ensure_student_finance_account_exists(student_id)

        with transaction() as conn:
            cursor = conn.cursor()

            # Get current balance and account_id
            cursor.execute('''
                SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?
            ''', (student_id,))
            account_result = cursor.fetchone()

            if not account_result:
                result['message'] = f"Finance account not found for student {student_id}"
                return result

            account_id, current_balance = account_result
            current_balance = float(current_balance)

            # Check sufficient balance
            if check_balance and current_balance < amount:
                result['message'] = f"Insufficient balance. Current: \u00a3{current_balance:.2f}, Required: \u00a3{amount:.2f}"
                return result

            # Calculate new balance
            new_balance = current_balance - amount

            # Update balance
            cursor.execute('''
                UPDATE student_finance_accounts
                SET balance = ?, updated_at = datetime('now')
                WHERE student_id = ?
            ''', (new_balance, student_id))

            # Record transaction in transactions table
            transaction_id = f"{transaction_source}_{transaction_ref}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            payment_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO transactions
                (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after,
                 description, processed_by)
                VALUES ('student_finance', ?, ?, 'payment', ?, ?, ?, ?, ?)
            ''', (account_id, student_id, amount, current_balance, new_balance,
                  f"[{transaction_source}] {description}", processed_by))

            # Also record in main payments table for finance GUI visibility
            cursor.execute('''
                INSERT INTO payments
                (student_id, amount, currency, payment_method, transaction_id, payment_date,
                 status, notes, created_by, created_at)
                VALUES (?, ?, 'GBP', 'Student Finance Account', ?, ?, 'completed', ?, ?, ?)
            ''', (student_id, amount, transaction_id, payment_date,
                  f"[{transaction_source}] {description}", processed_by, payment_date))
            payment_row_id = cursor.lastrowid

        # Auto-post to GL (status hardcoded 'completed'; cash has moved). Never raises.
        try:
            from education_system.systems.university.domain.finance.ledger import notify_ledger
            notify_ledger('payment', payment_row_id, posted_by=processed_by or 'finance_integration')
        except Exception as _e:
            logger.warning("ledger hook failed: %s", _e)

        result['success'] = True
        result['message'] = f"Payment of \u00a3{amount:.2f} processed successfully"
        result['new_balance'] = new_balance
        result['transaction_id'] = transaction_id

        logger.info(f"Finance account payment: {student_id} - \u00a3{amount:.2f} for {transaction_source} (Ref: {transaction_ref})")

        # Send payment receipt email
        result['receipt_sent'] = send_payment_receipt_email(
            student_id=student_id,
            amount=amount,
            description=description,
            transaction_source=transaction_source,
            transaction_id=transaction_id,
            balance_before=current_balance,
            balance_after=new_balance
        )

        # Check for low balance and send email
        if send_low_balance_alert and new_balance < LOW_BALANCE_THRESHOLD:
            result['email_sent'] = send_low_balance_email(student_id, new_balance)

        return result

    except sqlite3.Error as e:
        logger.error(f"Database error processing finance account payment: {e}")
        result['message'] = f"Database error: {e}"
        return result
    except Exception as e:
        logger.error(f"Error processing finance account payment: {e}")
        result['message'] = f"Error: {e}"
        return result

def top_up_student_finance_account(
    student_id: str,
    amount: float,
    payment_method: str,
    processed_by: str = "System",
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Top up a student's finance account balance.

    Args:
        student_id: Student ID
        amount: Amount to add
        payment_method: Method of top-up (e.g., "card", "cash", "bank_transfer")
        processed_by: Username of person processing the top-up
        description: Optional description

    Returns:
        Dictionary with success status, message, and new balance
    """
    result = {
        'success': False,
        'message': '',
        'new_balance': None
    }

    try:
        if amount <= 0:
            result['message'] = "Top-up amount must be positive"
            return result

        ensure_student_finance_account_exists(student_id)

        with transaction() as conn:
            cursor = conn.cursor()

            # Get current balance and account_id
            cursor.execute('''
                SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?
            ''', (student_id,))
            account_result = cursor.fetchone()

            if not account_result:
                result['message'] = f"Finance account not found for student {student_id}"
                return result

            account_id, current_balance = account_result
            current_balance = float(current_balance)
            new_balance = current_balance + amount

            # Update balance
            cursor.execute('''
                UPDATE student_finance_accounts
                SET balance = ?, updated_at = datetime('now')
                WHERE student_id = ?
            ''', (new_balance, student_id))

            # Record transaction
            desc = description or f'Top up via {payment_method}'
            cursor.execute('''
                INSERT INTO transactions
                (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after,
                 description, processed_by)
                VALUES ('student_finance', ?, ?, 'top_up', ?, ?, ?, ?, ?)
            ''', (account_id, student_id, amount, current_balance, new_balance, desc, processed_by))

        result['success'] = True
        result['message'] = f"Account topped up with \u00a3{amount:.2f}"
        result['new_balance'] = new_balance

        logger.info(f"Finance account top-up: {student_id} - \u00a3{amount:.2f} via {payment_method}")

        # Send top-up confirmation email
        result['email_sent'] = send_topup_confirmation_email(
            student_id=student_id,
            amount=amount,
            payment_method=payment_method,
            balance_before=current_balance,
            balance_after=new_balance
        )

        return result

    except sqlite3.Error as e:
        logger.error(f"Database error topping up finance account: {e}")
        result['message'] = f"Database error: {e}"
        return result
    except Exception as e:
        logger.error(f"Error topping up finance account: {e}")
        result['message'] = f"Error: {e}"
        return result

# ==================== Student-to-Student Transfers ====================

def _resolve_user_row_id(party_id: str) -> Optional[int]:
    """University users.id for a student_id/username, for inbox sender attribution."""
    try:
        with get_finance_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE student_id = ? OR username = ?',
                           (party_id, party_id))
            row = cursor.fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        return None

def send_transfer_receipt_email(
    student_id: str,
    recipient_name: str,
    recipient_id: str,
    amount: float,
    reference: str,
    reference_number: str,
    balance_before: float,
    balance_after: float
) -> bool:
    """
    Send a money-sent receipt email to the sender of a transfer.

    Uses the finance_commerce/finance/p2p_transfer_sent_receipt JSON template.

    Args:
        student_id: Sender's student ID (or username)
        recipient_name: Recipient's full name
        recipient_id: Recipient's student ID (or username)
        amount: Amount transferred
        reference: Sender-supplied reference (e.g. "Meal out")
        reference_number: Generated transfer reference number
        balance_before: Sender balance before the transfer
        balance_after: Sender balance after the transfer

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        student_info = get_student_info(student_id)
        if not student_info or not student_info.get('email'):
            logger.warning(f"Cannot send transfer receipt: No email found for student {student_id}")
            return False

        try:
            from education_system.systems.university.infrastructure.email.email_service import send_template_email

            # The template renders as body_html; user-supplied text must be
            # escaped for it. Plain-text renderings go through
            # html_to_plain_text(), which unescapes these entities again.
            template_vars = {
                'sender_name': html.escape(student_info.get('full_name', 'Student')),
                'sender_id': html.escape(str(student_id)),
                'recipient_name': html.escape(recipient_name),
                'recipient_id': html.escape(str(recipient_id)),
                'amount': f"{amount:.2f}",
                'reference': html.escape(reference),
                'reference_number': reference_number,
                'transfer_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'balance_before': f"{balance_before:.2f}",
                'balance_after': f"{balance_after:.2f}",
            }

            result = send_template_email(
                'finance_commerce/finance/p2p_transfer_sent_receipt',
                student_info['email'],
                template_vars
            )
            if result:
                logger.info(f"Transfer receipt email sent to {student_info['email']} for {reference_number}")
                return True
            logger.warning(f"Failed to send transfer receipt email to {student_info['email']}")
            return False

        except ImportError:
            logger.warning("Email service not available for transfer receipt")
            return False

    except Exception as e:
        logger.error(f"Error sending transfer receipt email: {e}")
        return False

def send_transfer_received_notification(
    recipient_id: str,
    recipient_name: str,
    sender_id: str,
    sender_name: str,
    amount: float,
    reference: str,
    reference_number: str
) -> bool:
    """
    Deliver an in-app inbox notification to the recipient of a transfer.

    The Notifications Hub is an unread inbox over the `messages` table, so
    this lands there via deliver_inbox_message. Body text comes from the
    finance_commerce/finance/p2p_transfer_received_notification JSON template.

    Returns:
        True if the notification was delivered, False otherwise
    """
    try:
        from education_system.systems.university.infrastructure.email.messages_inbox import deliver_inbox_message
        from education_system.systems.university.infrastructure.email.template_utils import render_template

        subject, body = render_template(
            'finance_commerce/finance/p2p_transfer_received_notification',
            {
                'recipient_name': recipient_name,
                'sender_name': sender_name,
                'sender_id': sender_id,
                'amount': f"{amount:.2f}",
                'reference': reference,
                'reference_number': reference_number,
                'transfer_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        )
        if subject is None or body is None:
            subject = f"You received £{amount:.2f} from {sender_name}"
            body = (
                f"{sender_name} ({sender_id}) has sent you £{amount:.2f}.\n\n"
                f"Reference: {reference}\n"
                f"Reference Number: {reference_number}"
            )

        message_id = deliver_inbox_message(
            recipient_id, subject, body,
            sender_id=_resolve_user_row_id(sender_id)
        )
        if message_id is not None:
            logger.info(f"Transfer notification delivered to {recipient_id} for {reference_number}")
            return True
        logger.warning(f"Failed to deliver transfer notification to {recipient_id}")
        return False

    except Exception as e:
        logger.error(f"Error delivering transfer notification: {e}")
        return False

def transfer_student_finance_funds(
    from_student_id: str,
    to_student_id: str,
    amount: float,
    reference: str,
    processed_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send money from one student finance account to another.

    Moves the amount between the two accounts and records both legs in the
    unified transactions ledger ('transfer_out' / 'transfer_in') under a
    shared generated reference number, all in one database transaction.
    The sender is emailed a receipt and the recipient gets an in-app
    notification.

    Args:
        from_student_id: Sender's student ID or username
        to_student_id: Recipient's student ID or username
        amount: Amount to send
        reference: Free-text reference for the transfer (e.g. "Meal out",
                   "Money owed") - required
        processed_by: Username recorded against the ledger rows (defaults
                      to the sender)

    Returns:
        Dictionary with:
            - success: bool - Whether the transfer completed
            - message: str - Status message
            - new_balance: float - Sender balance after transfer (if successful)
            - reference_number: str - Generated transfer reference (if successful)
            - recipient_name: str - Recipient's full name (if resolved)
            - email_sent: bool - Whether the sender receipt email was sent
            - notification_sent: bool - Whether the recipient notification was delivered
    """
    result = {
        'success': False,
        'message': '',
        'new_balance': None,
        'reference_number': None,
        'recipient_name': None,
        'email_sent': False,
        'notification_sent': False
    }

    try:
        try:
            amount = round(float(amount), 2)
        except (TypeError, ValueError):
            result['message'] = "Transfer amount must be a number"
            return result

        # not > 0 (rather than <= 0) so NaN is rejected too
        if not math.isfinite(amount) or not amount > 0:
            result['message'] = "Transfer amount must be positive"
            return result

        reference = (reference or '').strip()
        if not reference:
            result['message'] = "A reference is required (e.g. 'Meal out', 'Money owed')"
            return result

        from_ref = (from_student_id or '').strip()
        to_ref = (to_student_id or '').strip()
        if not from_ref or not to_ref:
            result['message'] = "Sender and recipient are required"
            return result

        from_info = get_student_info(from_ref)
        if not from_info:
            result['message'] = f"Sender not found: {from_ref}"
            return result

        to_info = get_student_info(to_ref)
        if not to_info:
            result['message'] = f"Recipient not found: {to_ref}"
            return result

        # Canonical account keys: student_id when the user has one, else
        # username - the same choice the bank GUI makes at login, so the
        # money lands on the account each user actually sees.
        from_id = from_info.get('student_id') or from_ref
        to_id = to_info.get('student_id') or to_ref

        if from_id == to_id:
            result['message'] = "Cannot send money to yourself"
            return result

        from_name = from_info.get('full_name') or from_id
        to_name = to_info.get('full_name') or to_id
        result['recipient_name'] = to_name

        ensure_student_finance_account_exists(from_id)
        ensure_student_finance_account_exists(to_id)

        reference_number = f"TRF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        processed_by = processed_by or from_id

        with transaction() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?
            ''', (from_id,))
            from_row = cursor.fetchone()
            cursor.execute('''
                SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?
            ''', (to_id,))
            to_row = cursor.fetchone()

            if not from_row:
                result['message'] = f"Finance account not found for student {from_id}"
                return result
            if not to_row:
                result['message'] = f"Finance account not found for student {to_id}"
                return result

            from_account_id, from_balance = from_row[0], float(from_row[1])
            to_account_id, to_balance = to_row[0], float(to_row[1])

            if from_balance < amount:
                result['message'] = f"Insufficient balance. Current: £{from_balance:.2f}, Required: £{amount:.2f}"
                return result

            from_new_balance = round(from_balance - amount, 2)
            to_new_balance = round(to_balance + amount, 2)

            cursor.execute('''
                UPDATE student_finance_accounts
                SET balance = ?, updated_at = datetime('now')
                WHERE student_id = ?
            ''', (from_new_balance, from_id))
            cursor.execute('''
                UPDATE student_finance_accounts
                SET balance = ?, updated_at = datetime('now')
                WHERE student_id = ?
            ''', (to_new_balance, to_id))

            cursor.execute('''
                INSERT INTO transactions
                (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after,
                 reference_type, reference_id, reference_number, description, processed_by)
                VALUES ('student_finance', ?, ?, 'transfer_out', ?, ?, ?, 'p2p_transfer', ?, ?, ?, ?)
            ''', (from_account_id, from_id, amount, from_balance, from_new_balance,
                  to_id, reference_number,
                  f"[Transfer] To {to_name} ({to_id}): {reference}", processed_by))

            cursor.execute('''
                INSERT INTO transactions
                (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after,
                 reference_type, reference_id, reference_number, description, processed_by)
                VALUES ('student_finance', ?, ?, 'transfer_in', ?, ?, ?, 'p2p_transfer', ?, ?, ?, ?)
            ''', (to_account_id, to_id, amount, to_balance, to_new_balance,
                  from_id, reference_number,
                  f"[Transfer] From {from_name} ({from_id}): {reference}", processed_by))

        result['success'] = True
        result['message'] = f"£{amount:.2f} sent to {to_name}"
        result['new_balance'] = from_new_balance
        result['reference_number'] = reference_number

        logger.info(
            f"Finance transfer: {from_id} -> {to_id} £{amount:.2f} "
            f"({reference_number}: {reference})"
        )

        result['email_sent'] = send_transfer_receipt_email(
            student_id=from_id,
            recipient_name=to_name,
            recipient_id=to_id,
            amount=amount,
            reference=reference,
            reference_number=reference_number,
            balance_before=from_balance,
            balance_after=from_new_balance
        )

        result['notification_sent'] = send_transfer_received_notification(
            recipient_id=to_id,
            recipient_name=to_name,
            sender_id=from_id,
            sender_name=from_name,
            amount=amount,
            reference=reference,
            reference_number=reference_number
        )

        return result

    except sqlite3.Error as e:
        logger.error(f"Database error transferring finance funds: {e}")
        result['message'] = f"Database error: {e}"
        return result
    except Exception as e:
        logger.error(f"Error transferring finance funds: {e}")
        result['message'] = f"Error: {e}"
        return result
