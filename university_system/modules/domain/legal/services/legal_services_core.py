"""
Legal Services Core - Business Logic Managers

Provides manager classes for legal case management, consultations,
documents, and payments with database operations.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid
import traceback

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity


# Service fee structure (in GBP)
SERVICE_FEES = {
    'consultation_30min': 25.00,
    'consultation_60min': 45.00,
    'document_review': 35.00,
    'contract_review': 50.00,
    'case_filing': 75.00,
    'immigration_consultation': 60.00,
    'ip_consultation': 55.00,
    'criminal_consultation': 70.00,
    'family_law_consultation': 50.00,
    'tenant_dispute': 40.00,
    'employment_consultation': 45.00,
    'consumer_rights': 30.00,
    'pro_bono': 0.00
}

# Case types available
CASE_TYPES = [
    'consultation', 'immigration', 'ip_patent', 'criminal',
    'family_law', 'pro_bono', 'tenant_dispute', 'employment',
    'consumer_rights', 'contract_review'
]

# Case statuses
CASE_STATUSES = ['open', 'in_progress', 'pending_review', 'closed']

# Consultation statuses
CONSULTATION_STATUSES = ['scheduled', 'completed', 'cancelled', 'no_show']

# Payment statuses
PAYMENT_STATUSES = ['pending', 'paid', 'refunded']


def init_legal_services_db():
    """Initialize legal services database tables"""
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            # Legal cases table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS legal_cases (
                    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_number TEXT UNIQUE NOT NULL,
                    client_id TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    client_email TEXT,
                    case_type TEXT NOT NULL,
                    case_title TEXT NOT NULL,
                    case_description TEXT,
                    status TEXT DEFAULT 'open',
                    priority TEXT DEFAULT 'normal',
                    assigned_lawyer TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    total_fees DECIMAL(10,2) DEFAULT 0.00,
                    amount_paid DECIMAL(10,2) DEFAULT 0.00,
                    created_by TEXT
                )
            ''')

            # Legal consultations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS legal_consultations (
                    consultation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER,
                    client_id TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    client_email TEXT,
                    consultation_type TEXT NOT NULL,
                    scheduled_date TEXT NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 30,
                    lawyer_id TEXT,
                    lawyer_name TEXT,
                    fee DECIMAL(10,2) DEFAULT 0.00,
                    payment_status TEXT DEFAULT 'pending',
                    payment_id TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'scheduled',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (case_id) REFERENCES legal_cases(case_id)
                )
            ''')

            # Legal documents table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS legal_documents (
                    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER,
                    document_type TEXT NOT NULL,
                    document_name TEXT NOT NULL,
                    file_path TEXT,
                    file_content TEXT,
                    version INTEGER DEFAULT 1,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (case_id) REFERENCES legal_cases(case_id)
                )
            ''')

            # Legal payments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS legal_payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER,
                    consultation_id INTEGER,
                    client_id TEXT NOT NULL,
                    client_email TEXT,
                    amount DECIMAL(10,2) NOT NULL,
                    payment_type TEXT NOT NULL,
                    payment_method TEXT,
                    transaction_reference TEXT,
                    status TEXT DEFAULT 'completed',
                    receipt_sent INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_by TEXT,
                    FOREIGN KEY (case_id) REFERENCES legal_cases(case_id),
                    FOREIGN KEY (consultation_id) REFERENCES legal_consultations(consultation_id)
                )
            ''')

            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_legal_cases_client ON legal_cases(client_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_legal_cases_status ON legal_cases(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_legal_consultations_date ON legal_consultations(scheduled_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_legal_payments_client ON legal_payments(client_id)')

            print("Legal services database initialized successfully")
            return True

    except sqlite3.Error as e:
        print(f"Error initializing legal services database: {e}")
        return False


def generate_case_number() -> str:
    """Generate unique case number"""
    timestamp = datetime.now().strftime('%Y%m%d')
    unique_id = uuid.uuid4().hex[:6].upper()
    return f"CASE-{timestamp}-{unique_id}"


class CaseManager:
    """Manager for legal case operations"""

    @staticmethod
    def create_case(client_id: str, client_name: str, client_email: str,
                    case_type: str, case_title: str, case_description: str = '',
                    priority: str = 'normal', assigned_lawyer: str = None,
                    created_by: str = None) -> Optional[int]:
        """Create a new legal case"""
        try:
            case_number = generate_case_number()

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO legal_cases
                    (case_number, client_id, client_name, client_email, case_type,
                     case_title, case_description, priority, assigned_lawyer, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (case_number, client_id, client_name, client_email, case_type,
                      case_title, case_description, priority, assigned_lawyer, created_by))

                case_id = cursor.lastrowid

            log_activity('create', 'legal_case', details={
                'case_id': case_id,
                'case_number': case_number,
                'client_name': client_name,
                'case_type': case_type
            })

            return case_id

        except sqlite3.Error as e:
            print(f"Error creating case: {e}")
            return None

    @staticmethod
    def get_case(case_id: int) -> Optional[Dict]:
        """Get case by ID"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM legal_cases WHERE case_id = ?', (case_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error getting case: {e}")
            return None

    @staticmethod
    def get_case_by_number(case_number: str) -> Optional[Dict]:
        """Get case by case number"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM legal_cases WHERE case_number = ?', (case_number,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error getting case by number: {e}")
            return None

    @staticmethod
    def get_all_cases(filters: Optional[Dict] = None) -> List[Dict]:
        """Get all cases with optional filters"""
        try:
            query = 'SELECT * FROM legal_cases WHERE 1=1'
            params = []

            if filters:
                if 'status' in filters and filters['status']:
                    query += ' AND status = ?'
                    params.append(filters['status'])
                if 'case_type' in filters and filters['case_type']:
                    query += ' AND case_type = ?'
                    params.append(filters['case_type'])
                if 'client_id' in filters and filters['client_id']:
                    query += ' AND client_id = ?'
                    params.append(filters['client_id'])
                if 'assigned_lawyer' in filters and filters['assigned_lawyer']:
                    query += ' AND assigned_lawyer = ?'
                    params.append(filters['assigned_lawyer'])
                if 'search' in filters and filters['search']:
                    query += ' AND (case_title LIKE ? OR client_name LIKE ? OR case_number LIKE ?)'
                    search_term = f"%{filters['search']}%"
                    params.extend([search_term, search_term, search_term])

            query += ' ORDER BY created_at DESC'

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting cases: {e}")
            return []

    @staticmethod
    def update_case(case_id: int, **updates) -> bool:
        """Update case fields"""
        try:
            if not updates:
                return False

            updates['updated_at'] = datetime.now().isoformat()

            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [case_id]

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(f'UPDATE legal_cases SET {set_clause} WHERE case_id = ?', values)

            log_activity('update', 'legal_case', details={'case_id': case_id, 'updates': list(updates.keys())})
            return True

        except sqlite3.Error as e:
            print(f"Error updating case: {e}")
            return False

    @staticmethod
    def close_case(case_id: int, closed_by: str = None) -> bool:
        """Close a legal case"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE legal_cases
                    SET status = 'closed', closed_at = ?, updated_at = ?
                    WHERE case_id = ?
                ''', (datetime.now().isoformat(), datetime.now().isoformat(), case_id))

            log_activity('close', 'legal_case', details={'case_id': case_id, 'closed_by': closed_by})
            return True

        except sqlite3.Error as e:
            print(f"Error closing case: {e}")
            return False

    @staticmethod
    def get_case_statistics() -> Dict:
        """Get case statistics for reporting"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Total cases by status
                cursor.execute('''
                    SELECT status, COUNT(*) as count
                    FROM legal_cases
                    GROUP BY status
                ''')
                status_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Total cases by type
                cursor.execute('''
                    SELECT case_type, COUNT(*) as count
                    FROM legal_cases
                    GROUP BY case_type
                ''')
                type_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Revenue statistics
                cursor.execute('''
                    SELECT SUM(total_fees) as total_fees, SUM(amount_paid) as total_paid
                    FROM legal_cases
                ''')
                revenue = cursor.fetchone()

                # Cases this month
                first_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
                cursor.execute('''
                    SELECT COUNT(*) FROM legal_cases
                    WHERE created_at >= ?
                ''', (first_of_month,))
                cases_this_month = cursor.fetchone()[0]

                return {
                    'by_status': status_counts,
                    'by_type': type_counts,
                    'total_fees': revenue[0] or 0,
                    'total_paid': revenue[1] or 0,
                    'cases_this_month': cases_this_month,
                    'total_cases': sum(status_counts.values())
                }

        except sqlite3.Error as e:
            print(f"Error getting case statistics: {e}")
            return {}


class ConsultationManager:
    """Manager for legal consultation operations"""

    @staticmethod
    def schedule_consultation(client_id: str, client_name: str, client_email: str,
                              consultation_type: str, scheduled_date: str,
                              scheduled_time: str, duration_minutes: int = 30,
                              lawyer_name: str = None, case_id: int = None,
                              notes: str = '') -> Optional[int]:
        """Schedule a new consultation"""
        try:
            # Calculate fee based on consultation type and duration
            if consultation_type == 'pro_bono':
                fee = 0.00
            elif duration_minutes <= 30:
                fee = SERVICE_FEES.get(f'{consultation_type}_consultation', SERVICE_FEES['consultation_30min'])
            else:
                fee = SERVICE_FEES.get(f'{consultation_type}_consultation', SERVICE_FEES['consultation_60min'])

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO legal_consultations
                    (case_id, client_id, client_name, client_email, consultation_type,
                     scheduled_date, scheduled_time, duration_minutes, lawyer_name, fee, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (case_id, client_id, client_name, client_email, consultation_type,
                      scheduled_date, scheduled_time, duration_minutes, lawyer_name, fee, notes))

                consultation_id = cursor.lastrowid

            log_activity('schedule', 'legal_consultation', details={
                'consultation_id': consultation_id,
                'client_name': client_name,
                'date': scheduled_date,
                'time': scheduled_time
            })

            return consultation_id

        except sqlite3.Error as e:
            print(f"Error scheduling consultation: {e}")
            return None

    @staticmethod
    def get_consultation(consultation_id: int) -> Optional[Dict]:
        """Get consultation by ID"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM legal_consultations WHERE consultation_id = ?', (consultation_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error getting consultation: {e}")
            return None

    @staticmethod
    def get_all_consultations(filters: Optional[Dict] = None) -> List[Dict]:
        """Get all consultations with optional filters"""
        try:
            query = 'SELECT * FROM legal_consultations WHERE 1=1'
            params = []

            if filters:
                if 'status' in filters and filters['status']:
                    query += ' AND status = ?'
                    params.append(filters['status'])
                if 'payment_status' in filters and filters['payment_status']:
                    query += ' AND payment_status = ?'
                    params.append(filters['payment_status'])
                if 'scheduled_date' in filters and filters['scheduled_date']:
                    query += ' AND scheduled_date = ?'
                    params.append(filters['scheduled_date'])
                if 'client_id' in filters and filters['client_id']:
                    query += ' AND client_id = ?'
                    params.append(filters['client_id'])

            query += ' ORDER BY scheduled_date DESC, scheduled_time DESC'

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting consultations: {e}")
            return []

    @staticmethod
    def update_consultation(consultation_id: int, **updates) -> bool:
        """Update consultation fields"""
        try:
            if not updates:
                return False

            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [consultation_id]

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(f'UPDATE legal_consultations SET {set_clause} WHERE consultation_id = ?', values)

            log_activity('update', 'legal_consultation', details={'consultation_id': consultation_id})
            return True

        except sqlite3.Error as e:
            print(f"Error updating consultation: {e}")
            return False

    @staticmethod
    def cancel_consultation(consultation_id: int, reason: str = '') -> bool:
        """Cancel a consultation"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE legal_consultations
                    SET status = 'cancelled', notes = notes || ' | Cancelled: ' || ?
                    WHERE consultation_id = ?
                ''', (reason, consultation_id))

            log_activity('cancel', 'legal_consultation', details={
                'consultation_id': consultation_id,
                'reason': reason
            })
            return True

        except sqlite3.Error as e:
            print(f"Error cancelling consultation: {e}")
            return False

    @staticmethod
    def get_upcoming_consultations(days: int = 7) -> List[Dict]:
        """Get consultations scheduled in the next N days"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM legal_consultations
                    WHERE scheduled_date >= ? AND scheduled_date <= ?
                    AND status = 'scheduled'
                    ORDER BY scheduled_date, scheduled_time
                ''', (today, end_date))
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting upcoming consultations: {e}")
            return []


class DocumentManager:
    """Manager for legal document operations"""

    @staticmethod
    def create_document(case_id: int, document_type: str, document_name: str,
                        file_path: str = None, file_content: str = None,
                        created_by: str = None, notes: str = '') -> Optional[int]:
        """Create a new legal document"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO legal_documents
                    (case_id, document_type, document_name, file_path, file_content, created_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (case_id, document_type, document_name, file_path, file_content, created_by, notes))

                document_id = cursor.lastrowid

            log_activity('create', 'legal_document', details={
                'document_id': document_id,
                'case_id': case_id,
                'document_name': document_name
            })

            return document_id

        except sqlite3.Error as e:
            print(f"Error creating document: {e}")
            return None

    @staticmethod
    def get_document(document_id: int) -> Optional[Dict]:
        """Get document by ID"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM legal_documents WHERE document_id = ?', (document_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error getting document: {e}")
            return None

    @staticmethod
    def get_case_documents(case_id: int) -> List[Dict]:
        """Get all documents for a case"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM legal_documents
                    WHERE case_id = ?
                    ORDER BY created_at DESC
                ''', (case_id,))
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting case documents: {e}")
            return []

    @staticmethod
    def get_document_history(document_name: str, case_id: int) -> List[Dict]:
        """Get version history for a document"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM legal_documents
                    WHERE document_name = ? AND case_id = ?
                    ORDER BY version DESC
                ''', (document_name, case_id))
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting document history: {e}")
            return []

    @staticmethod
    def update_document(document_id: int, **updates) -> bool:
        """Update document with new version"""
        try:
            # Get current version
            current = DocumentManager.get_document(document_id)
            if not current:
                return False

            # Increment version if content changed
            if 'file_content' in updates or 'file_path' in updates:
                updates['version'] = current['version'] + 1

            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [document_id]

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(f'UPDATE legal_documents SET {set_clause} WHERE document_id = ?', values)

            return True

        except sqlite3.Error as e:
            print(f"Error updating document: {e}")
            return False


class PaymentManager:
    """Manager for legal payment operations"""

    @staticmethod
    def record_payment(client_id: str, client_email: str, amount: float,
                       payment_type: str, payment_method: str,
                       case_id: int = None, consultation_id: int = None,
                       processed_by: str = None) -> Optional[int]:
        """Record a payment for legal services"""
        try:
            transaction_ref = f"LEG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

            with transaction() as conn:
                cursor = conn.cursor()

                # Insert into legal_payments
                cursor.execute('''
                    INSERT INTO legal_payments
                    (case_id, consultation_id, client_id, client_email, amount,
                     payment_type, payment_method, transaction_reference, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (case_id, consultation_id, client_id, client_email, amount,
                      payment_type, payment_method, transaction_ref, processed_by))

                payment_id = cursor.lastrowid

                # Update case amount_paid if case_id provided
                if case_id:
                    cursor.execute('''
                        UPDATE legal_cases
                        SET amount_paid = amount_paid + ?, updated_at = ?
                        WHERE case_id = ?
                    ''', (amount, datetime.now().isoformat(), case_id))

                # Update consultation payment status if consultation_id provided
                if consultation_id:
                    cursor.execute('''
                        UPDATE legal_consultations
                        SET payment_status = 'paid', payment_id = ?
                        WHERE consultation_id = ?
                    ''', (str(payment_id), consultation_id))

                # Also record in main payments table for finance system integration
                try:
                    cursor.execute('''
                        INSERT INTO payments
                        (student_id, amount, payment_method, payment_date, status, notes, created_by, created_at)
                        VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)
                    ''', (client_id, amount, payment_method, datetime.now().strftime('%Y-%m-%d'),
                          f'Legal Services Fee - {transaction_ref}', processed_by, datetime.now().isoformat()))
                except sqlite3.OperationalError:
                    # payments table may not exist in all setups
                    pass

            log_activity('payment', 'legal_services', details={
                'payment_id': payment_id,
                'client_id': client_id,
                'amount': amount,
                'transaction_ref': transaction_ref
            })

            return payment_id

        except sqlite3.Error as e:
            print(f"Error recording payment: {e}")
            return None

    @staticmethod
    def get_payment(payment_id: int) -> Optional[Dict]:
        """Get payment by ID"""
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM legal_payments WHERE payment_id = ?', (payment_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error getting payment: {e}")
            return None

    @staticmethod
    def get_all_payments(filters: Optional[Dict] = None) -> List[Dict]:
        """Get all payments with optional filters"""
        try:
            query = 'SELECT * FROM legal_payments WHERE 1=1'
            params = []

            if filters:
                if 'client_id' in filters and filters['client_id']:
                    query += ' AND client_id = ?'
                    params.append(filters['client_id'])
                if 'case_id' in filters and filters['case_id']:
                    query += ' AND case_id = ?'
                    params.append(filters['case_id'])
                if 'status' in filters and filters['status']:
                    query += ' AND status = ?'
                    params.append(filters['status'])
                if 'start_date' in filters and filters['start_date']:
                    query += ' AND DATE(created_at) >= ?'
                    params.append(filters['start_date'])
                if 'end_date' in filters and filters['end_date']:
                    query += ' AND DATE(created_at) <= ?'
                    params.append(filters['end_date'])

            query += ' ORDER BY created_at DESC'

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting payments: {e}")
            return []

    @staticmethod
    def mark_receipt_sent(payment_id: int) -> bool:
        """Mark receipt as sent for a payment"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE legal_payments SET receipt_sent = 1
                    WHERE payment_id = ?
                ''', (payment_id,))
            return True
        except sqlite3.Error as e:
            print(f"Error marking receipt sent: {e}")
            return False

    @staticmethod
    def process_refund(payment_id: int, reason: str = '', processed_by: str = None) -> bool:
        """Process a refund for a payment"""
        try:
            payment = PaymentManager.get_payment(payment_id)
            if not payment:
                return False

            with transaction() as conn:
                cursor = conn.cursor()

                # Update payment status
                cursor.execute('''
                    UPDATE legal_payments
                    SET status = 'refunded'
                    WHERE payment_id = ?
                ''', (payment_id,))

                # Update case amount_paid if applicable
                if payment['case_id']:
                    cursor.execute('''
                        UPDATE legal_cases
                        SET amount_paid = amount_paid - ?, updated_at = ?
                        WHERE case_id = ?
                    ''', (payment['amount'], datetime.now().isoformat(), payment['case_id']))

                # Update consultation payment status if applicable
                if payment['consultation_id']:
                    cursor.execute('''
                        UPDATE legal_consultations
                        SET payment_status = 'refunded'
                        WHERE consultation_id = ?
                    ''', (payment['consultation_id'],))

            log_activity('refund', 'legal_payment', details={
                'payment_id': payment_id,
                'amount': payment['amount'],
                'reason': reason,
                'processed_by': processed_by
            })

            return True

        except sqlite3.Error as e:
            print(f"Error processing refund: {e}")
            return False

    @staticmethod
    def get_revenue_statistics(start_date: str = None, end_date: str = None) -> Dict:
        """Get revenue statistics for reporting"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                base_query = 'SELECT * FROM legal_payments WHERE status = "completed"'
                params = []

                if start_date:
                    base_query += ' AND DATE(created_at) >= ?'
                    params.append(start_date)
                if end_date:
                    base_query += ' AND DATE(created_at) <= ?'
                    params.append(end_date)

                # Total revenue
                cursor.execute(f'''
                    SELECT SUM(amount) FROM legal_payments
                    WHERE status = 'completed'
                    {' AND DATE(created_at) >= ?' if start_date else ''}
                    {' AND DATE(created_at) <= ?' if end_date else ''}
                ''', params)
                total_revenue = cursor.fetchone()[0] or 0

                # Revenue by payment type
                cursor.execute(f'''
                    SELECT payment_type, SUM(amount) as total, COUNT(*) as count
                    FROM legal_payments
                    WHERE status = 'completed'
                    {' AND DATE(created_at) >= ?' if start_date else ''}
                    {' AND DATE(created_at) <= ?' if end_date else ''}
                    GROUP BY payment_type
                ''', params)
                by_type = {row[0]: {'total': row[1], 'count': row[2]} for row in cursor.fetchall()}

                # Revenue by method
                cursor.execute(f'''
                    SELECT payment_method, SUM(amount) as total, COUNT(*) as count
                    FROM legal_payments
                    WHERE status = 'completed'
                    {' AND DATE(created_at) >= ?' if start_date else ''}
                    {' AND DATE(created_at) <= ?' if end_date else ''}
                    GROUP BY payment_method
                ''', params)
                by_method = {row[0]: {'total': row[1], 'count': row[2]} for row in cursor.fetchall()}

                # Refunds
                cursor.execute(f'''
                    SELECT SUM(amount), COUNT(*)
                    FROM legal_payments
                    WHERE status = 'refunded'
                    {' AND DATE(created_at) >= ?' if start_date else ''}
                    {' AND DATE(created_at) <= ?' if end_date else ''}
                ''', params)
                refund_data = cursor.fetchone()

                return {
                    'total_revenue': total_revenue,
                    'by_payment_type': by_type,
                    'by_payment_method': by_method,
                    'total_refunds': refund_data[0] or 0,
                    'refund_count': refund_data[1] or 0,
                    'net_revenue': total_revenue - (refund_data[0] or 0)
                }

        except sqlite3.Error as e:
            print(f"Error getting revenue statistics: {e}")
            return {}


def calculate_service_fee(service_type: str, duration_minutes: int = 30) -> float:
    """Calculate fee for a service type"""
    if service_type == 'pro_bono':
        return 0.00

    # Check for specific service fee
    fee_key = f'{service_type}_consultation'
    if fee_key in SERVICE_FEES:
        base_fee = SERVICE_FEES[fee_key]
    else:
        # Use default consultation fees
        base_fee = SERVICE_FEES['consultation_30min'] if duration_minutes <= 30 else SERVICE_FEES['consultation_60min']

    # Adjust for longer durations
    if duration_minutes > 60:
        extra_30min_blocks = (duration_minutes - 60) // 30
        base_fee += extra_30min_blocks * (SERVICE_FEES['consultation_30min'] * 0.75)

    return round(base_fee, 2)


def generate_invoice_text(case: Dict, payments: List[Dict], services: List[str]) -> str:
    """Generate invoice text for a case"""
    invoice_date = datetime.now().strftime('%Y-%m-%d')

    total_fees = case.get('total_fees', 0)
    total_paid = sum(p['amount'] for p in payments if p['status'] == 'completed')
    balance_due = total_fees - total_paid

    invoice = f"""
================================================================================
                        UNIVERSITY LEGAL SERVICES
                              INVOICE
================================================================================

Invoice Date:    {invoice_date}
Case Number:     {case['case_number']}
Client:          {case['client_name']}
Email:           {case.get('client_email', 'N/A')}

--------------------------------------------------------------------------------
SERVICES PROVIDED
--------------------------------------------------------------------------------
"""

    for service in services:
        invoice += f"  - {service}\n"

    invoice += f"""
--------------------------------------------------------------------------------
PAYMENT SUMMARY
--------------------------------------------------------------------------------
Total Fees:          GBP {total_fees:.2f}
Amount Paid:         GBP {total_paid:.2f}
Balance Due:         GBP {balance_due:.2f}

--------------------------------------------------------------------------------
PAYMENT HISTORY
--------------------------------------------------------------------------------
"""

    for p in payments:
        invoice += f"  {p['created_at'][:10]}  {p['payment_type']:<20}  GBP {p['amount']:>8.2f}  [{p['status']}]\n"

    invoice += """
================================================================================
Thank you for using University Legal Services.
For questions, contact legal@university.edu
================================================================================
"""

    return invoice
